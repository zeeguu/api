from datetime import datetime, timedelta

from sqlalchemy.orm import joinedload
from wordstats import Word

from zeeguu.core.model import Phrase, ExerciseOutcome, UserPreference
from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user_word import UserWord

ONE_DAY = 60 * 24

DEFAULT_MAX_WORDS_TO_SCHEDULE = 20
MAX_WORDS_TO_SCHEDULE_CAP = 100  # Maximum allowed value to prevent SQL LIMIT errors


class BasicSRSchedule(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "basic_sr_schedule"

    id = db.Column(db.Integer, primary_key=True)

    user_word = db.relationship(UserWord)
    user_word_id = db.Column(db.Integer, db.ForeignKey(UserWord.id), nullable=False)

    next_practice_time = db.Column(db.DateTime, nullable=False)
    consecutive_correct_answers = db.Column(db.Integer)
    cooling_interval = db.Column(db.Integer)

    def __init__(self, user_word=None, user_word_id=None):
        if user_word_id:
            self.user_word_id = user_word_id
        else:
            self.user_word = user_word
        self.next_practice_time = datetime.now()
        self.consecutive_correct_answers = 0
        self.cooling_interval = 0

    def set_meaning_as_learned(self, db_session):
        self.user_word.learned_time = datetime.now()
        db_session.add(self.user_word)
        db_session.delete(self)
        db_session.commit()

    def there_was_no_need_for_practice_on_date(self, date: datetime = None):
        # a user might have arrived here by doing the
        # bookmarks in a text for a second time...
        # in general, as long as they didn't wait for the
        # cooldown period, they might have arrived to do
        # the exercise again; but it should not count
        return _get_end_of_date(date) < self.next_practice_time

    def update_schedule(self, db_session, correctness):
        raise NotImplementedError

    def get_max_interval(self):
        raise NotImplementedError

    def get_cooling_interval_dictionary(self):
        raise NotImplementedError

    @classmethod
    def clear_user_word_schedule(cls, db_session, user_word):
        schedule = cls.find_by_user_word(user_word)
        if schedule is not None:
            db_session.delete(schedule)
            db_session.commit()

    @classmethod
    def find_or_create(cls, db_session, user_word):
        raise NotImplementedError

    @classmethod
    def find_by_user_word(cls, user_word):
        try:
            result = cls.query.filter(cls.user_word_id == user_word.id).one()
            return result
        except Exception as e:
            return None

    # TODO: There's no reason for this duplicating the behavior above.
    @classmethod
    def find(cls, user_word):

        results = cls.query.filter_by(user_word=user_word).all()

        if len(results) == 1:
            return results[0]

        if len(results) > 1:
            raise Exception(
                f"More than one Bookmark schedule entry found for {user_word.id}"
            )
        return None

    @classmethod
    def update(cls, db_session, user_word, outcome, time: datetime = None):
        if not time:
            time = datetime.now()

        if outcome == ExerciseOutcome.OTHER_FEEDBACK:
            from zeeguu.core.model.bookmark_user_preference import UserWordExPreference

            schedule = cls.find(user_word)
            if schedule:
                db_session.delete(schedule)

            user_word.fit_for_study = 0

            # Since the user has explicitly given feedback, this should
            # be recorded as a user preference.
            user_word.user_preference = UserWordExPreference.DONT_USE_IN_EXERCISES
            db_session.add(user_word)

            return

        correctness = ExerciseOutcome.is_correct(outcome)

        # Do we have more words scheduled than the user prefers?
        more_scheduled_words_than_user_prefers = cls.scheduled_user_words_count(
            user_word.user
        ) >= UserPreference.get_max_words_to_schedule(user_word.user)

        schedule = cls.find(user_word)

        if schedule and schedule.there_was_no_need_for_practice_on_date(time):
            # nothing to update in this case
            return

        if not schedule and more_scheduled_words_than_user_prefers:
            # we are not adding this word to scheduled words
            return

        # pipeline is not full, and the word was not scheduled before
        if not schedule and not more_scheduled_words_than_user_prefers:
            schedule = cls.find_or_create(db_session, user_word)

        schedule.update_schedule(db_session, correctness, time)

    @classmethod
    def user_words_not_scheduled(cls, user, limit):
        # Import here to avoid circular imports
        from zeeguu.core.model.bookmark import Bookmark

        unscheduled_meanings = (
            UserWord.query
            .options(
                # Eager load meaning and its relations
                joinedload(UserWord.meaning)
                .joinedload(Meaning.origin)
                .joinedload(Phrase.language),
                joinedload(UserWord.meaning)
                .joinedload(Meaning.translation)
                .joinedload(Phrase.language),
                # Eager load preferred_bookmark and its relations
                joinedload(UserWord.preferred_bookmark)
                .joinedload(Bookmark.text),
                joinedload(UserWord.preferred_bookmark)
                .joinedload(Bookmark.context),
                joinedload(UserWord.preferred_bookmark)
                .joinedload(Bookmark.source),
            )
            .filter(UserWord.user_id == user.id)
            .outerjoin(BasicSRSchedule)
            .filter(UserWord.learned_time == None)
            .filter(UserWord.fit_for_study == 1)
            .join(Meaning, UserWord.meaning_id == Meaning.id)
            .join(Phrase, Meaning.origin_id == Phrase.id)
            .filter(Phrase.language_id == user.learned_language_id)
            .filter(BasicSRSchedule.cooling_interval == None)
            .order_by(
                -Phrase.rank.desc()
            )  # By using the negative for rank, we ensure NULL is last.
        )
        if limit is None:
            return unscheduled_meanings.all()
        else:
            return unscheduled_meanings.limit(limit).all()

    @classmethod
    def user_words_to_study(cls, user):
        """
        Looks at all the bookmarks available to the user and prioritizes them
        based on the Rank of the words.

        This way the user will be practicing the easiest words first, and
        newer words are introduced as soon as they are translated. Using
        this method, we do not need to explicitly schedule new words.

        Currently, we prioritize bookmarks in the following way:
         1. Words that are most common in the language (utilizing the word rank in the db
         2. Words that are closest to being learned (indicated by `cooling_interval`,
        the highest the closest it is)
        """

        max_words_to_schedule = UserPreference.get_max_words_to_schedule(user)

        scheduled_candidates = cls.scheduled_words_due_today(
            user, max_words_to_schedule
        )

        scheduled_for_this_user = cls.scheduled_user_words_count(user)
        if scheduled_for_this_user < max_words_to_schedule:
            count_needed = max_words_to_schedule - scheduled_for_this_user
            unscheduled_bookmarks = cls.user_words_not_scheduled(user, count_needed)

            scheduled_candidates = scheduled_candidates + unscheduled_bookmarks

        # Batch load all schedules to avoid N+1 queries during sorting
        from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord
        user_word_ids = [uw.id for uw in scheduled_candidates]
        if user_word_ids:
            schedules = FourLevelsPerWord.query.filter(
                FourLevelsPerWord.user_word_id.in_(user_word_ids)
            ).all()
            schedule_map = {s.user_word_id: s for s in schedules}
        else:
            schedule_map = {}

        sorted_candidates = sorted(
            scheduled_candidates, key=lambda x: priority_by_rank(x, schedule_map)
        )
        return sorted_candidates

    @classmethod
    def _scheduled_user_words_query(cls, user, language=None):
        _lang_to_look_at = language.id if language else user.learned_language_id

        # Import here to avoid circular imports
        from zeeguu.core.model.bookmark import Bookmark
        from zeeguu.core.model.text import Text
        from zeeguu.core.model.bookmark_context import BookmarkContext

        query = (
            UserWord.query.join(cls)
            .options(
                # Eager load meaning and its relations
                joinedload(UserWord.meaning)
                .joinedload(Meaning.origin)
                .joinedload(Phrase.language),
                joinedload(UserWord.meaning)
                .joinedload(Meaning.translation)
                .joinedload(Phrase.language),
                # Eager load preferred_bookmark and its relations
                joinedload(UserWord.preferred_bookmark)
                .joinedload(Bookmark.text),
                joinedload(UserWord.preferred_bookmark)
                .joinedload(Bookmark.context),
                joinedload(UserWord.preferred_bookmark)
                .joinedload(Bookmark.source),
            )
            .filter(UserWord.user_id == user.id)
            .filter(UserWord.fit_for_study == 1)
            .join(Meaning, UserWord.meaning_id == Meaning.id)
            .join(Phrase, Meaning.origin_id == Phrase.id)
            .filter(Phrase.language_id == _lang_to_look_at)
            .filter(BasicSRSchedule.id != None)
        )
        return query

    @classmethod
    def scheduled_words_due_today(cls, user, limit=None):

        query = cls._scheduled_user_words_query(user)
        query = query.filter(cls.next_practice_time < _get_end_of_today())

        # The scheduled bookmarks are sorted by the most common in the language and
        # then by cooling interval, meaning the words that are closest to being learned
        # come before the ones that are just learned.
        query.order_by(
            -Phrase.rank.desc(), cls.cooling_interval.desc()
        )  # By using the negative for rank, we ensure NULL is last.

        if limit is not None:
            query = query.limit(limit)

        return query.all()

    @classmethod
    def scheduled_user_words(cls, user, language=None, required_count=None):
        query = cls._scheduled_user_words_query(user, language)
        if required_count is not None:
            query = query.limit(required_count)
        meanings = query.all()
        return meanings

    @classmethod
    def scheduled_user_words_count(cls, user) -> int:
        query = cls._scheduled_user_words_query(user)
        return query.distinct(UserWord.id).count()

    @classmethod
    def schedule_for_user(cls, user_id):
        schedule = (
            BasicSRSchedule.query.join(UserWord)
            .filter(UserWord.user_id == user_id)
            .join(Meaning, UserWord.meaning_id == Meaning.id)
            .join(Phrase, Meaning.origin_id == Phrase.id)
            .all()
        )
        return schedule

    @classmethod
    def print_schedule_for_user(cls, user_id):
        schedule = cls.schedule_for_user(user_id)
        res = ""
        for each in schedule:
            res += (
                each.user_word.meaning.origin.content
                + " "
                + str(each.next_practice_time)
                + " \n"
            )

    @classmethod
    def next_practice_time_for_user(cls, user):
        """
        Returns the datetime of the next scheduled word for practice.
        Returns None if no words are scheduled.
        """
        from zeeguu.core.model.bookmark import Bookmark

        result = (
            cls.query.join(UserWord)
            .filter(UserWord.user_id == user.id)
            .filter(UserWord.fit_for_study == 1)
            .join(Meaning, UserWord.meaning_id == Meaning.id)
            .join(Phrase, Meaning.origin_id == Phrase.id)
            .filter(Phrase.language_id == user.learned_language_id)
            .order_by(cls.next_practice_time.asc())
            .first()
        )

        if result:
            return result.next_practice_time
        return None


def priority_by_rank(user_word, schedule_map=None):
    """
    Calculate priority for sorting user words.

    Args:
        user_word: The UserWord to calculate priority for
        schedule_map: Optional dict mapping user_word_id to schedule (avoids N+1 queries)
    """
    # Use database rank directly instead of Word.stats() lookup (faster)
    word_rank = user_word.meaning.origin.rank or Phrase.IMPOSSIBLE_RANK

    # Use pre-loaded schedule if available, otherwise query
    if schedule_map is not None:
        basic_sr_schedule = schedule_map.get(user_word.id)
    else:
        basic_sr_schedule = BasicSRSchedule.find_by_user_word(user_word)

    cooling_interval = (
        basic_sr_schedule.cooling_interval
        if basic_sr_schedule and basic_sr_schedule.cooling_interval is not None
        else -1
    )
    return word_rank, -cooling_interval


def _get_end_of_date(date):
    """
    Retrieves midnight date of the following date,
    essentially ensures we get all the bookmarks
    scheduled for the date day. < (date+1)
    """

    # Get tomorrow date
    tomorrows_date = (date + timedelta(days=1)).date()
    # Create an object that matches midnight of next day
    return datetime.combine(tomorrows_date, datetime.min.time())


def _get_end_of_today():
    return _get_end_of_date(datetime.now())
