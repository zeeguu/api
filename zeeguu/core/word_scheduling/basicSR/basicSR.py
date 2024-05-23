from zeeguu.core.model import Bookmark, UserWord, ExerciseOutcome

from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.learning_cycle import LearningCycle
from zeeguu.core.model import UserPreference

from zeeguu.core.model import db

from datetime import datetime, timedelta

ONE_DAY = 60 * 24
MAX_INTERVAL_8_DAY = 8 * ONE_DAY

NEXT_COOLING_INTERVAL_ON_SUCCESS = {
    0: ONE_DAY,
    ONE_DAY: 2 * ONE_DAY,
    2 * ONE_DAY: 4 * ONE_DAY,
    4 * ONE_DAY: 8 * ONE_DAY,
}

# Reverse the process
DECREASE_COOLING_INTERVAL_ON_FAIL = {
    v: k for k, v in NEXT_COOLING_INTERVAL_ON_SUCCESS.items()
}
# If at 0, we don't decrease it further.
DECREASE_COOLING_INTERVAL_ON_FAIL[0] = 0


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
        self.bookmark.learned = True
        self.bookmark.learned_time = datetime.now()
        db_session.add(self.bookmark)
        db_session.commit()
        db_session.delete(self)
        db_session.commit()

    def update_schedule(self, db_session, correctness):
        learning_cycle = self.bookmark.learning_cycle

        productive_exercises_enabled = (
            UserPreference.is_productive_exercises_preference_enabled(
                self.bookmark.user
            )
        )
        if correctness:
            if self.cooling_interval == MAX_INTERVAL_8_DAY:
                if (
                    learning_cycle == LearningCycle.RECEPTIVE
                    and productive_exercises_enabled
                ):
                    # Switch learning_cycle to productive knowledge and reset cooling interval
                    self.bookmark.learning_cycle = LearningCycle.PRODUCTIVE
                    self.cooling_interval = 0
                    db.session.add(self.bookmark)
                    db.session.commit()
                    return
                else:
                    self.set_bookmark_as_learned(db_session)
                    return

            # Use the same logic as when selecting bookmarks
            # Avoid case where if schedule at 01-01-2024 11:00 and user does it at
            # 01-01-2024 10:00 the status is not updated.
            if self.get_end_of_today() < self.next_practice_time:
                # a user might have arrived here by doing the
                # bookmarks in a text for a second time...
                # in general, as long as they didn't wait for the
                # cooldown perio, they might have arrived to do
                # the exercise again; but it should not count
                return
            # Since we can now loose the streak on day 8,
            # we might have to repeat it a few times to learn it.
            new_cooling_interval = NEXT_COOLING_INTERVAL_ON_SUCCESS.get(
                self.cooling_interval, MAX_INTERVAL_8_DAY
            )
            self.consecutive_correct_answers += 1
        else:
            # Decrease the cooling interval to the previous bucket
            new_cooling_interval = DECREASE_COOLING_INTERVAL_ON_FAIL[
                self.cooling_interval
            ]
            # Should we allow the user to "recover" their schedule
            # in the same day?
            # next_practice_date = datetime.now()
            self.consecutive_correct_answers = 0

        self.cooling_interval = new_cooling_interval
        next_practice_date = datetime.now() + timedelta(minutes=new_cooling_interval)
        self.next_practice_time = next_practice_date

        db_session.add(self)
        db_session.commit()

    @classmethod
    def update(cls, db_session, bookmark, outcome):

        if outcome == ExerciseOutcome.OTHER_FEEDBACK:
            print("Deleting Schedule for Word!")
            schedule = cls.find_or_create(db_session, bookmark)
            bookmark.fit_for_study = 0
            db_session.add(bookmark)
            db_session.delete(schedule)
            db_session.commit()
            return

        correctness = (
            outcome == ExerciseOutcome.CORRECT
            or outcome
            in [
                "TC",
                "TTC",
                "TTTC",
            ]  # allow for a few translations before hitting the correct; they work like hints
            or outcome == "HC"  # if it's correct after hint it should still be fine
        )
        schedule = cls.find_or_create(db_session, bookmark)
        if schedule.next_practice_time > cls.get_end_of_today():
            # The user is doing the word before it was scheduled.
            # We do not update the schedule if that's the case.
            # This can happen when they practice words from the
            # Article.
            return
        schedule.update_schedule(db_session, correctness)

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
    def find_or_create(cls, db_session, bookmark):

        results = cls.query.filter_by(bookmark=bookmark).all()
        print(results)
        if len(results) == 1:
            print(len(results))
            print("getting the first element in results")
            return results[0]

        if len(results) > 1:
            raise Exception(
                f"More than one Bookmark schedule entry found for {bookmark.id}"
            )

        # create a new one
        schedule = cls(bookmark)
        bookmark.learning_cycle = LearningCycle.RECEPTIVE
        db_session.add_all([schedule, bookmark])
        db_session.commit()
        return schedule

    @classmethod
    def priority_bookmarks_to_study(cls, user, required_count):
        """
        Prioritizes the bookmarks to study. To randomize the
        exercise order utilize the Frontend assignBookmarksToExercises.js

        The original logic is kept in bookmarks_to_study as it is called to
        get similar_words to function as distractors in the exercises.

        Currently, we prioritize bookmarks in the following way:
        1. Words that are closest to being learned (indicated by `cooling_interval`, the highest the closest it is)
        2. Words that are most common in the language (utilizing the word rank in the db)
        """

        def sorting_properties(bookmark):
            cooling_interval = (
                cls.query.filter_by(bookmark=bookmark).one().cooling_interval
            )
            user_word = UserWord.query.filter_by(id=bookmark.origin_id).one()
            word_rank = user_word.rank
            if word_rank is None:
                word_rank = UserWord.IMPOSSIBLE_RANK
            return -cooling_interval, word_rank

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

        scheduled_candidates = scheduled_candidates_query.all()

        # Remove possible duplicated words from the list
        # - The user might have multiple translations of the same word in different
        # contexts that are saved as different bookmarks
        # - In a session, a word should only show up once.
        # TR: With the Topics a util function will be introduced that does this.
        # We also need to ensure that we use the lower. Otherwise they might be duplicated
        # due to different casing.
        bookmark_set = set()
        candidates_no_duplicates = []
        for bookmark in scheduled_candidates:
            b_word = bookmark.origin.word.lower()
            if not (b_word in bookmark_set):
                candidates_no_duplicates.append(bookmark)
                bookmark_set.add(b_word)

        sorted_candidates = sorted(
            candidates_no_duplicates, key=lambda x: sorting_properties(x)
        )

        return sorted_candidates[:required_count]

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
