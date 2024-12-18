from zeeguu.core.model import Bookmark, UserWord, ExerciseOutcome

from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.learning_cycle import LearningCycle
from zeeguu.core.model import UserPreference

from zeeguu.core.model import db

from datetime import datetime, timedelta

ONE_DAY = 60 * 24


class BasicSRSchedule(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "basic_sr_schedule"

    id = db.Column(db.Integer, primary_key=True)

    bookmark = db.relationship(Bookmark)
    bookmark_id = db.Column(db.Integer, db.ForeignKey(Bookmark.id), nullable=False)

    next_practice_time = db.Column(db.DateTime, nullable=False)
    consecutive_correct_answers = db.Column(db.Integer)
    cooling_interval = db.Column(db.Integer)

    def __init__(self, bookmark=None, bookmark_id=None):
        if bookmark_id:
            self.bookmark_id = bookmark_id
        else:
            self.bookmark = bookmark
        self.next_practice_time = datetime.now()
        self.consecutive_correct_answers = 0
        self.cooling_interval = 0

    def set_bookmark_as_learned(self, db_session):
        self.bookmark.learned_time = datetime.now()
        db_session.add(self.bookmark)
        db_session.delete(self)
        db_session.commit()

    def there_was_no_need_for_practice_today(self):
        # a user might have arrived here by doing the
        # bookmarks in a text for a second time...
        # in general, as long as they didn't wait for the
        # cooldown period, they might have arrived to do
        # the exercise again; but it should not count
        return self.get_end_of_today() < self.next_practice_time

    def update_schedule(self, db_session, correctness):
        raise NotImplementedError

    def get_max_interval(self):
        raise NotImplementedError

    def get_cooling_interval_dictionary(self):
        raise NotImplementedError

    @classmethod
    def clear_bookmark_schedule(cls, db_session, bookmark):
        schedule = cls.find_by_bookmark(bookmark)
        if schedule is not None:
            db_session.delete(schedule)
            db_session.commit()

    @classmethod
    def get_end_of_today(cls):
        """
        Retrieves midnight date of the following date,
        essentially ensures we get all the bookmarks
        scheduled for the current day. < (cur_day+1)
        """
        # Get tomorrow date
        tomorrows_date = (datetime.now() + timedelta(days=1)).date()
        # Create an object that matches midnight of next day
        return datetime.combine(tomorrows_date, datetime.min.time())

    @classmethod
    def find_by_bookmark(cls, bookmark):
        try:
            result = cls.query.filter(cls.bookmark_id == bookmark.id).one()
            return result
        except Exception as e:
            return None

    @classmethod
    def find_or_create(cls, db_session, bookmark):
        raise NotImplementedError

    @classmethod
    def find(cls, bookmark):

        results = cls.query.filter_by(bookmark=bookmark).all()

        if len(results) == 1:
            return results[0]

        if len(results) > 1:
            raise Exception(
                f"More than one Bookmark schedule entry found for {bookmark.id}"
            )
        return None

    @classmethod
    def update(cls, db_session, bookmark, outcome):

        if outcome == ExerciseOutcome.OTHER_FEEDBACK:
            from zeeguu.core.model.bookmark_user_preference import UserWordExPreference

            schedule = cls.find_or_create(db_session, bookmark)
            bookmark.fit_for_study = 0
            ## Since the user has explicitly given feedback, this should
            # be recorded as a user preference.
            bookmark.user_preference = UserWordExPreference.DONT_USE_IN_EXERCISES
            db_session.add(bookmark)
            db_session.delete(schedule)
            db_session.commit()
            return

        correctness = ExerciseOutcome.is_correct(outcome)
        schedule = cls.find_or_create(db_session, bookmark)
        if schedule.there_was_no_need_for_practice_today():
            return

        schedule.update_schedule(db_session, correctness)
        db_session.commit()

    @classmethod
    def get_scheduled_bookmarks_for_user(cls, user, limit):
        end_of_day = cls.get_end_of_today()
        # Get the candidates, words that are to practice
        scheduled_candidates_query = (
            Bookmark.query.join(cls)
            .filter(Bookmark.user_id == user.id)
            .join(UserWord, Bookmark.origin_id == UserWord.id)
            .filter(UserWord.language_id == user.learned_language_id)
            .filter(cls.next_practice_time < end_of_day)
        )

        # If productive exercises are disabled, exclude bookmarks with learning_cycle of 2
        if not UserPreference.is_productive_exercises_preference_enabled(user):
            scheduled_candidates_query = scheduled_candidates_query.filter(
                Bookmark.learning_cycle == LearningCycle.RECEPTIVE
            )
        # The scheduled bookmarks are sorted by the most common in the language and
        # then by cooling interval, meaning the words that are closest to being learned
        # come before the ones that are just learned.
        scheduled_candidates_query.order_by(
            -UserWord.rank.desc(), cls.cooling_interval.desc()
        )  # By using the negative for rank, we ensure NULL is last.
        if limit is None:
            return scheduled_candidates_query.all()
        else:
            return scheduled_candidates_query.limit(limit).all()

    @classmethod
    def get_unscheduled_bookmarks_for_user(cls, user, limit):
        unscheduled_bookmarks = (
            Bookmark.query.filter(Bookmark.user_id == user.id)
            .outerjoin(BasicSRSchedule)
            .filter(Bookmark.learned_time == None)
            .filter(Bookmark.fit_for_study == 1)
            .join(UserWord, Bookmark.origin_id == UserWord.id)
            .filter(UserWord.language_id == user.learned_language_id)
            .filter(BasicSRSchedule.cooling_interval == None)
            .order_by(
                -UserWord.rank.desc()
            )  # By using the negative for rank, we ensure NULL is last.
        )
        if limit is None:
            return unscheduled_bookmarks.all()
        else:
            return unscheduled_bookmarks.limit(limit).all()

    @classmethod
    def remove_duplicated_bookmarks(cls, bookmark_list):
        bookmark_set = set()
        # Remove possible duplicated words from the list
        # - The user might have multiple translations of the same word in different
        # contexts that are saved as different bookmarks
        # - In a session, a word should only show up once.
        # TR: With the Topics a util function will be introduced that does this.
        # We also need to ensure that we use the lower. Otherwise they might be duplicated
        # due to different casing.
        candidates_no_duplicates = []
        for bookmark in bookmark_list:
            b_word = bookmark.origin.word.lower()
            if not (b_word in bookmark_set):
                candidates_no_duplicates.append(bookmark)
                bookmark_set.add(b_word)
        return candidates_no_duplicates

    @classmethod
    def all_bookmarks_priority_to_study(cls, user, limit):
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

        def priority_by_rank(bookmark):
            # If this is updated remember to update the order_by in
            # get_scheduled_bookmarks_for_user and get_unscheduled_bookmarks_for_user
            bookmark_info = bookmark.json_serializable_dict()
            cooling_interval = bookmark_info["cooling_interval"]
            cooling_interval = cooling_interval if cooling_interval is not None else -1
            word_rank = bookmark_info["origin_rank"]
            if word_rank == "":
                word_rank = UserWord.IMPOSSIBLE_RANK
            return word_rank, -cooling_interval

        scheduled_candidates = cls.get_scheduled_bookmarks_for_user(user, limit)
        unscheduled_bookmarks = cls.get_unscheduled_bookmarks_for_user(user, limit)

        all_possible_bookmarks = scheduled_candidates + unscheduled_bookmarks
        no_duplicate_bookmarks = cls.remove_duplicated_bookmarks(all_possible_bookmarks)
        sorted_candidates = sorted(
            no_duplicate_bookmarks, key=lambda x: priority_by_rank(x)
        )
        return sorted_candidates

    @classmethod
    def priority_scheduled_bookmarks_to_study(cls, user, limit):
        """
        Prioritizes the bookmarks to study. To randomize the
        exercise order utilize the Frontend assignBookmarksToExercises.js

        The original logic is kept in bookmarks_to_study as it is called to
        get similar_words to function as distractors in the exercises.

        To update the order of bookmarks look at the order_by in
        get_scheduled_bookmarks_for_user
        """

        scheduled_candidates = cls.get_scheduled_bookmarks_for_user(user, limit)
        no_duplicate_bookmarks = cls.remove_duplicated_bookmarks(scheduled_candidates)

        return no_duplicate_bookmarks

    @classmethod
    def bookmarks_to_study(cls, user, required_count):
        end_of_day = cls.get_end_of_today()
        # Get the candidates, words that are to practice
        scheduled = (
            Bookmark.query.join(cls)
            .filter(Bookmark.user_id == user.id)
            .join(UserWord, Bookmark.origin_id == UserWord.id)
            .filter(UserWord.language_id == user.learned_language_id)
            .filter(cls.next_practice_time < end_of_day)
            .limit(required_count)
            .all()
        )
        return scheduled

    @classmethod
    def bookmarks_in_pipeline(cls, user):
        # Get the candidates, words that are to practice
        scheduled = (
            Bookmark.query.join(cls)
            .filter(Bookmark.user_id == user.id)
            .join(UserWord, Bookmark.origin_id == UserWord.id)
            .filter(UserWord.language_id == user.learned_language_id)
            .all()
        )
        return scheduled

    @classmethod
    def total_bookmarks_in_pipeline(cls, user) -> int:
        total_pipeline_bookmarks = (
            Bookmark.query.join(cls)
            .filter(Bookmark.user_id == user.id)
            .join(UserWord, Bookmark.origin_id == UserWord.id)
            .filter(UserWord.language_id == user.learned_language_id)
            .count()
        )
        return total_pipeline_bookmarks

    @classmethod
    def schedule_for_user(cls, user_id):
        schedule = (
            BasicSRSchedule.query.join(Bookmark)
            .filter(Bookmark.user_id == user_id)
            .join(UserWord, Bookmark.origin_id == UserWord.id)
            .all()
        )
        return schedule

    @classmethod
    def print_schedule_for_user(cls, user_id):
        schedule = cls.schedule_for_user(user_id)
        res = ""
        for each in schedule:
            res += (
                each.bookmark.origin.word + " " + str(each.next_practice_time) + " \n"
            )
