from datetime import datetime, timedelta

from wordstats import Word

from zeeguu.core.model import Phrase, ExerciseOutcome, UserPreference
from zeeguu.core.model import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user_meaning import UserMeaning

ONE_DAY = 60 * 24

DEFAULT_MAX_WORDS_TO_SCHEDULE = 20


class BasicSRSchedule(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "basic_sr_schedule"

    __mapper_args__ = {
        "polymorphic_identity": "basic_sr_schedule",
    }

    id = db.Column(db.Integer, primary_key=True)

    user_meaning = db.relationship(UserMeaning, backref="basic_sr_schedule")
    user_meaning_id = db.Column(
        db.Integer, db.ForeignKey(UserMeaning.id), nullable=False
    )

    next_practice_time = db.Column(db.DateTime, nullable=False)
    consecutive_correct_answers = db.Column(db.Integer)
    cooling_interval = db.Column(db.Integer)

    def __init__(self, user_meaning=None, user_meaning_id=None):
        if user_meaning_id:
            self.user_meaning_id = user_meaning_id
        else:
            self.user_meaning = user_meaning
        self.next_practice_time = datetime.now()
        self.consecutive_correct_answers = 0
        self.cooling_interval = 0

    def set_meaning_as_learned(self, db_session):
        self.user_meaning.learned_time = datetime.now()
        db_session.add(self.user_meaning)
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
    def clear_meaning_schedule(cls, db_session, user_meaning):
        schedule = cls.find_by_user_meaning(user_meaning)
        if schedule is not None:
            db_session.delete(schedule)
            db_session.commit()

    @classmethod
    def find_or_create(cls, db_session, bookmark):
        raise NotImplementedError

    @classmethod
    def find_by_user_meaning(cls, user_meaning):
        try:
            result = cls.query.filter(cls.user_meaning_id == user_meaning.id).one()
            return result
        except Exception as e:
            return None

    # TODO: There's no reason for this duplicating the behavior above.
    @classmethod
    def find(cls, user_meaning):

        results = cls.query.filter_by(user_meaning=user_meaning).all()

        if len(results) == 1:
            return results[0]

        if len(results) > 1:
            raise Exception(
                f"More than one Bookmark schedule entry found for {user_meaning.id}"
            )
        return None

    @classmethod
    def update(cls, db_session, user_meaning, outcome, time: datetime = None):
        if not time:
            time = datetime.now()

        if outcome == ExerciseOutcome.OTHER_FEEDBACK:
            from zeeguu.core.model.bookmark_user_preference import UserWordExPreference

            schedule = cls.find(user_meaning)
            if schedule:
                db_session.delete(schedule)

            user_meaning.fit_for_study = 0

            # Since the user has explicitly given feedback, this should
            # be recorded as a user preference.
            user_meaning.user_preference = UserWordExPreference.DONT_USE_IN_EXERCISES
            db_session.add(user_meaning)

            db_session.commit()
            return

        correctness = ExerciseOutcome.is_correct(outcome)

        # Do we have more words scheduled than the user prefers?
        more_scheduled_words_than_user_prefers = cls.scheduled_meanings_count(
            user_meaning.user
        ) >= UserPreference.get_max_words_to_schedule(user_meaning.user)

        schedule = cls.find(user_meaning)

        if schedule and schedule.there_was_no_need_for_practice_on_date(time):
            # nothing to update in this case
            return

        if not schedule and more_scheduled_words_than_user_prefers:
            # we are not adding this word to scheduled words
            return

        # pipeline is not full, and the word was not scheduled before
        if not schedule and not more_scheduled_words_than_user_prefers:
            schedule = cls.find_or_create(db_session, user_meaning)

        schedule.update_schedule(db_session, correctness, time)
        db_session.commit()

    @classmethod
    def user_meanings_not_scheduled(cls, user, limit):
        from zeeguu.core.model import Bookmark

        unscheduled_meanings = (
            UserMeaning.query.join(Bookmark)
            .filter(UserMeaning.user_id == user.id)
            .outerjoin(BasicSRSchedule)
            .filter(UserMeaning.learned_time == None)
            .filter(UserMeaning.fit_for_study == 1)
            .join(Meaning, UserMeaning.meaning_id == Meaning.id)
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
    def user_meanings_to_study(cls, user):
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

        scheduled_candidates = cls.scheduled_meanings_due_today(
            user, max_words_to_schedule
        )

        scheduled_for_this_user = cls.scheduled_meanings_count(user)
        if scheduled_for_this_user < max_words_to_schedule:
            count_needed = max_words_to_schedule - scheduled_for_this_user
            unscheduled_bookmarks = cls.user_meanings_not_scheduled(user, count_needed)

            scheduled_candidates = scheduled_candidates + unscheduled_bookmarks

        sorted_candidates = sorted(
            scheduled_candidates, key=lambda x: priority_by_rank(x)
        )
        return sorted_candidates

    @classmethod
    def _scheduled_meanings_query(cls, user, language=None):
        _lang_to_look_at = language.id if language else user.learned_language_id
        from zeeguu.core.model import Bookmark

        query = (
            UserMeaning.query.join(cls)
            .filter(UserMeaning.user_id == user.id)
            .join(Meaning, UserMeaning.meaning_id == Meaning.id)
            .join(Phrase, Meaning.origin_id == Phrase.id)
            .join(Bookmark, Bookmark.user_meaning_id == UserMeaning.id)
            .filter(Phrase.language_id == _lang_to_look_at)
            .filter(BasicSRSchedule.id is not None)
        )
        return query

    @classmethod
    def scheduled_meanings_due_today(cls, user, limit=None):

        query = cls._scheduled_meanings_query(user)
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
    def scheduled_meanings(cls, user, language=None, required_count=None):
        query = cls._scheduled_meanings_query(user, language)
        if required_count is not None:
            query = query.limit(required_count)
        meanings = query.all()
        return meanings

    @classmethod
    def scheduled_meanings_count(cls, user) -> int:
        query = cls._scheduled_meanings_query(user)
        return query.count()

    @classmethod
    def schedule_for_user(cls, user_id):
        schedule = (
            BasicSRSchedule.query.join(UserMeaning)
            .filter(UserMeaning.user_id == user_id)
            .join(Meaning, UserMeaning.meaning_id == Meaning.id)
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
                each.user_meaning.meaning.origin.content
                + " "
                + str(each.next_practice_time)
                + " \n"
            )


def priority_by_rank(user_meaning):
    # If this is updated remember to update the order_by in
    # get_scheduled_bookmarks_for_user and get_unscheduled_bookmarks_for_user

    word_info = Word.stats(
        user_meaning.meaning.origin.content,
        user_meaning.meaning.origin.language.code,
    )

    cooling_interval = (
        user_meaning.basic_sr_schedule[0].cooling_interval
        if user_meaning.basic_sr_schedule
        and user_meaning.basic_sr_schedule[0].cooling_interval is not None
        else -1
    )
    word_rank = word_info.rank if word_info.rank else Phrase.IMPOSSIBLE_RANK
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
