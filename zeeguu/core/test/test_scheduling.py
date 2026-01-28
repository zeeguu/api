from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.exercise_session_rule import ExerciseSessionRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.scheduler_rule import SchedulerRule
from zeeguu.core.model.user import User

from zeeguu.core.model.db import db
from datetime import datetime, timedelta

from zeeguu.core.word_scheduling import ONE_DAY

db_session = db.session

ONE_DAY_LATER = timedelta(days=1, seconds=1)
ONE_SECOND_LATER = timedelta(days=0, seconds=1)
TWO_DAYS_LATER = timedelta(days=2, seconds=1)
FOUR_DAYS_LATER = timedelta(days=4, seconds=1)
EIGHT_DAYS_LATER = timedelta(days=8, seconds=1)

ONE_DAY_COOLING = ONE_DAY
TWO_DAYS_COOLING = 2 * ONE_DAY
FOUR_DAYS_COOLING = 4 * ONE_DAY
EIGHT_DAYS_COOLING = 8 * ONE_DAY


class SchedulerTest(ModelTestMixIn):
    """
    Scheduler tests using class-level setup to share user.
    Each test creates its own bookmarks as needed.
    """

    @classmethod
    def setUpClass(cls):
        """Create shared user once for all tests."""
        from zeeguu.core.test.conftest import get_shared_app, get_mock, init_fixtures_once

        cls.app = get_shared_app()
        get_mock()

        with cls.app.app_context():
            init_fixtures_once()

            cls.user_rule = UserRule()
            cls._user_id = cls.user_rule.user.id

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests in this class."""
        from zeeguu.core.test.conftest import cleanup_tables

        with cls.app.app_context():
            db_session.close()
            cleanup_tables()

    def setUp(self):
        """Per-test setup - get fresh user reference."""
        from faker import Faker
        self.faker = Faker()
        self.four_levels_user = User.find_by_id(self._user_id)

    def tearDown(self):
        """Per-test teardown - don't clean tables, done in tearDownClass."""
        pass

    def run(self, result=None):
        """Run test within app context."""
        with self.app.app_context():
            super(ModelTestMixIn, self).run(result)

    # ================================================================================================================
    # Note: Helper functions are at the bottom of the class definition
    # ================================================================================================================

    def test_level_schedule_is_created(self):
        """
        Testing if FourLevelsSchedule creates the schedule once the bookmark is practiced.
        """

        bookmark = BookmarkRule(self.four_levels_user).bookmark

        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, datetime.now()
        )
        self.assert_schedule(schedule, 0, 1, ONE_DAY_COOLING, 1)

        bookmark_2 = BookmarkRule(self.four_levels_user).bookmark

        schedule = self._new_schedule_after_exercise(
            bookmark_2, OutcomeRule().wrong, datetime.now()
        )
        self.assert_schedule(schedule, 0, 1, 0, 0)

    def test_level_full_cycle(self):
        """
        Test the full progression through all the 4 levels with 2 intervals each.
        All values are hardset and asserted to ensure we catch any changes to the
        scheduler.
        """

        bookmark = BookmarkRule(self.four_levels_user).bookmark

        first_date = datetime.now()
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, first_date
        )
        self.assert_schedule(schedule, 0, 1, ONE_DAY, 1)

        second_date = first_date + ONE_DAY_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, second_date
        )
        self.assert_schedule(schedule, 0, 1, TWO_DAYS_COOLING, 2)

        third_date = second_date + TWO_DAYS_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, third_date
        )
        self.assert_schedule(schedule, 0, 2, 0, 3)

        fourth_date = third_date + ONE_SECOND_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, fourth_date
        )
        self.assert_schedule(schedule, 0, 2, ONE_DAY, 4)

        fifth_date = fourth_date + ONE_DAY_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, fifth_date
        )
        self.assert_schedule(schedule, 0, 2, TWO_DAYS_COOLING, 5)

        sixth_date = fifth_date + TWO_DAYS_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, sixth_date
        )
        self.assert_schedule(schedule, 0, 3, 0, 6)

        seventh_date = sixth_date + ONE_SECOND_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, seventh_date
        )
        self.assert_schedule(schedule, 0, 3, ONE_DAY_COOLING, 7)

        eighth_date = seventh_date + ONE_DAY_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, eighth_date
        )
        self.assert_schedule(schedule, 0, 3, TWO_DAYS_COOLING, 8)

        nineth_date = eighth_date + TWO_DAYS_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, nineth_date
        )
        self.assert_schedule(schedule, 0, 4, 0, 9)

        tenth_date = nineth_date + ONE_SECOND_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, tenth_date
        )
        self.assert_schedule(schedule, 0, 4, ONE_DAY_COOLING, 10)

        eleventh_date = tenth_date + ONE_DAY_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, eleventh_date
        )
        self.assert_schedule(schedule, 0, 4, TWO_DAYS_COOLING, 11)

        twelth_date = eleventh_date + TWO_DAYS_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, twelth_date
        )

        # Should be learned!
        assert bookmark.user_word.learned_time is not None

    def test_level_two_correct_exercises_in_a_day(self):
        """
        When a user does the same bookmark with a positive outcome in a day,
        the scheduler should not update.
        """

        bookmark = BookmarkRule(self.four_levels_user).bookmark

        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, datetime.now()
        )
        self.assert_schedule(schedule, 0, 1, ONE_DAY_COOLING, 1)

        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, datetime.now()
        )

        self.assert_schedule(schedule, 0, 1, ONE_DAY_COOLING, 1)

    def test_level_wrong(self):
        """
        If a user gets the bookmark wrong they should go one interval down in the
        LevelSR.
        """

        bookmark = BookmarkRule(self.four_levels_user).bookmark

        first_date = datetime.now()
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, first_date
        )
        self.assert_schedule(schedule, 0, 1, ONE_DAY_COOLING, 1)

        second_date = first_date + ONE_DAY_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, second_date
        )
        self.assert_schedule(schedule, 0, 1, TWO_DAYS_COOLING, 2)

        third_date = second_date + TWO_DAYS_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().wrong, third_date
        )

        self.assert_schedule(schedule, 0, 1, ONE_DAY_COOLING, 0)
        fourth_date = third_date + ONE_DAY_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark, OutcomeRule().correct, fourth_date
        )

        self.assert_schedule(schedule, 0, 1, TWO_DAYS_COOLING, 1)

    def test_level_doesnt_go_back_to_lower_level(self):
        """
        Test if when a user moves to a new level, they don't go down a level if
        they commit a mistake.
        """

        random_bookmark = BookmarkRule(self.four_levels_user).bookmark

        first_date = datetime.now()
        schedule = self._new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, first_date
        )
        self.assert_schedule(schedule, 0, 1, ONE_DAY_COOLING, 1)

        second_date = first_date + ONE_DAY_LATER
        schedule = self._new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, second_date
        )

        self.assert_schedule(schedule, 0, 1, TWO_DAYS_COOLING, 2)

        third_date = second_date + TWO_DAYS_LATER
        schedule = self._new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, third_date
        )

        self.assert_schedule(schedule, 0, 2, 0, 3)

        fourth_date = third_date + ONE_SECOND_LATER
        schedule = self._new_schedule_after_exercise(
            random_bookmark, OutcomeRule().wrong, fourth_date
        )

        self.assert_schedule(schedule, 0, 2, 0, 0)

    # ================================================================================================================
    # A few helper functions
    # ================================================================================================================
    def assert_schedule(
        self,
        schedule,
        expected_cycle,
        expected_level,
        expected_cooling,
        expected_consecutive_corrects,
    ):
        # Note: expected cycle is legacy and not being used
        # tests whether the bookmark schedule is in the expected cycle, level, cooling interval, etc.
        # ML: I've switched from assert to assertEqual because otherwise my IDE was complaining that there
        # was no reason for this to be a method, because it was not using at all the reference to 'self'
        # Alternative was to extract it as a function at the top of the file, but it felt more like a method
        self.assertEqual(schedule.user_word.level, expected_level)
        self.assertEqual(schedule.cooling_interval, expected_cooling)
        self.assertEqual(
            schedule.consecutive_correct_answers, expected_consecutive_corrects
        )

    def _simulate_progression_up_to_productive_cycle(self, bookmark):

        first_date = datetime.now()

        self._new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            first_date,
        )

        second_date = first_date + ONE_DAY_LATER

        self._new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            second_date,
        )

        third_date = second_date + TWO_DAYS_LATER
        self._new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            third_date,
        )

        fourth_date = third_date + FOUR_DAYS_LATER
        self._new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            fourth_date,
        )

        fifth_date = fourth_date + EIGHT_DAYS_LATER
        schedule = self._new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            fifth_date,
        )
        return fifth_date, schedule

    def _new_schedule_after_exercise(self, bookmark, outcome, date: datetime = None):
        exercise_session = ExerciseSessionRule(self.four_levels_user).exerciseSession
        exercise = ExerciseRule(exercise_session, outcome, date).exercise
        bookmark.user_word.report_exercise_outcome(
            db_session,
            exercise.source.source,
            exercise.outcome.outcome,
            exercise.solving_speed,
            exercise_session.id,
            "",
            time=date,
        )

        schedule = SchedulerRule(
            bookmark.user_word.get_scheduler(), bookmark.user_word, db_session
        ).schedule
        return schedule
