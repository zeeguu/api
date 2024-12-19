from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.exercise_session_rule import ExerciseSessionRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.scheduler_rule import SchedulerRule

from zeeguu.core.model import db
from datetime import datetime, timedelta

from zeeguu.core.word_scheduling import ONE_DAY

db_session = db.session


class SchedulerTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        # A user with the two cycles rule
        self.user_rule_cycle = UserRule()
        self.two_cycles_user = self.user_rule_cycle.user
        self.two_cycles_bookmark1 = BookmarkRule(self.two_cycles_user).bookmark
        self.two_cycles_bookmark2 = BookmarkRule(self.two_cycles_user).bookmark

        # A user with the four levels
        self.user_rule_levels = UserRule()
        self.four_levels_user = self.user_rule_levels.user
        self.four_levels_user.invitation_code = "exercise_levels"

        db_session.add(self.four_levels_user)
        db_session.commit()

    # ================================================================================================================
    # Note: Helper functions are at the bottom of the class definition
    # ================================================================================================================
    def test_learning_cycle_schedule_is_created(self):

        bookmark = self.two_cycles_bookmark1

        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            datetime.now(),
        )

        self.assert_schedule(schedule, 1, 0, ONE_DAY, 1)

        bookmark2 = self.two_cycles_bookmark2
        schedule = self._get_new_schedule_after_exercise(
            bookmark2,
            OutcomeRule().wrong,
            datetime.now(),
        )

        self.assert_schedule(schedule, 1, 0, 0, 0)

    def test_learning_cycle_two_correct_exercises_in_a_day(self):
        """
        When a user does the same bookmark with a positive outcome in a day,
        the scheduler should not update.
        """

        bookmark = BookmarkRule(self.two_cycles_user).bookmark

        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            datetime.now(),
        )

        self.assert_schedule(schedule, 1, 0, ONE_DAY, 1)

        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            datetime.now(),
        )

        self.assert_schedule(schedule, 1, 0, ONE_DAY, 1)

    def test_learning_cycle_full_cycle(self):
        """
        Tests the entire learning cycle process, all the values are hardset
        to ensure they match the expectation.

        """

        first_date = datetime.now()
        bookmark = self.two_cycles_bookmark1

        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            first_date,
        )

        self.assert_schedule(schedule, 1, 0, ONE_DAY, 1)

        second_date = first_date + timedelta(days=1, seconds=1)

        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            second_date,
        )

        self.assert_schedule(schedule, 1, 0, 2 * ONE_DAY, 2)

        third_date = second_date + timedelta(days=2, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            third_date,
        )

        self.assert_schedule(schedule, 1, 0, 4 * ONE_DAY, 3)

        fourth_date = third_date + timedelta(days=4, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            fourth_date,
        )

        self.assert_schedule(schedule, 1, 0, 8 * ONE_DAY, 4)

        fifth_date = fourth_date + timedelta(days=8, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            fifth_date,
        )

        self.assert_schedule(schedule, 2, 0, 0, 5)

        six_date = fifth_date + timedelta(days=0, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            six_date,
        )

        self.assert_schedule(schedule, 2, 0, ONE_DAY, 6)

        seven_date = six_date + timedelta(days=1, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            seven_date,
        )

        self.assert_schedule(schedule, 2, 0, 2 * ONE_DAY, 7)

        eight_date = seven_date + timedelta(days=2, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            eight_date,
        )

        self.assert_schedule(schedule, 2, 0, 4 * ONE_DAY, 8)

        nine_date = eight_date + timedelta(days=4, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            nine_date,
        )

        self.assert_schedule(schedule, 2, 0, 8 * ONE_DAY, 9)

        ten_date = nine_date + timedelta(days=8, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            ten_date,
        )

        assert bookmark.learned_time

    def test_learning_cycle_wrong(self):
        """
        Test the scheduler when the user gets an error.
        The schedule should go back one interval, and not reset completely.
        """

        random_bookmark = BookmarkRule(self.two_cycles_user).bookmark
        first_date = datetime.now()

        schedule = self._get_new_schedule_after_exercise(
            random_bookmark,
            OutcomeRule().correct,
            first_date,
        )

        self.assert_schedule(schedule, 1, 0, ONE_DAY, 1)

        second_date = first_date + timedelta(days=1, seconds=1)
        print(schedule.next_practice_time, second_date)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark,
            OutcomeRule().wrong,
            second_date,
        )

        self.assert_schedule(schedule, 1, 0, 0, 0)

        third_date = second_date + timedelta(days=0, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark,
            OutcomeRule().correct,
            third_date,
        )

        self.assert_schedule(schedule, 1, 0, ONE_DAY, 1)

        fourth_date = third_date + timedelta(days=1, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark,
            OutcomeRule().correct,
            fourth_date,
        )

        self.assert_schedule(schedule, 1, 0, 2 * ONE_DAY, 2)

        fifth_date = fourth_date + timedelta(days=2, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark,
            OutcomeRule().wrong,
            fifth_date,
        )

        self.assert_schedule(schedule, 1, 0, ONE_DAY, 0)

    def test_learning_cycle_productive_doesnt_go_down_to_receptive(self):
        """
        A bookmark shouldn't go down a cycle, meaning if we get to
        productive then the bookmark doesn't go back to receptive.
        """

        random_bookmark = BookmarkRule(self.two_cycles_user).bookmark
        last_date, schedule = self._helper_simulate_progression_up_to_productive_cycle(
            random_bookmark
        )
        assert schedule.consecutive_correct_answers == 5
        assert schedule.cooling_interval == 0

        fifth_date = last_date + timedelta(days=0, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark,
            OutcomeRule().wrong,
            fifth_date,
        )

        assert random_bookmark.learning_cycle == 2
        assert schedule.consecutive_correct_answers == 0
        assert schedule.cooling_interval == 0

    def test_level_schedule_is_created(self):
        """
        Testing if FourLevelsSchedule creates the schedule once the bookmark is practiced.
        """

        random_bookmark = BookmarkRule(self.four_levels_user).bookmark

        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, datetime.now()
        )

        self.assert_schedule(schedule, 0, 1, ONE_DAY, 1)

        random_bookmark_2 = BookmarkRule(self.four_levels_user).bookmark

        schedule = self._get_new_schedule_after_exercise(
            random_bookmark_2, OutcomeRule().wrong, datetime.now()
        )

        self.assert_schedule(schedule, 0, 1, 0, 0)

    def test_level_full_cycle(self):
        """
        Test the full progression through all the 4 levels with 2 intervals each.
        All values are hardset and asserted to ensure we catch any changes to the
        scheduler.
        """

        random_bookmark = BookmarkRule(self.four_levels_user).bookmark

        first_date = datetime.now()
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, first_date
        )

        self.assert_schedule(schedule, 0, 1, ONE_DAY, 1)

        second_date = first_date + timedelta(days=1, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, second_date
        )

        self.assert_schedule(schedule, 0, 1, 2 * ONE_DAY, 2)

        third_date = second_date + timedelta(days=2, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, third_date
        )

        self.assert_schedule(schedule, 0, 2, 0, 3)

        fourth_date = third_date + timedelta(days=0, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, fourth_date
        )

        self.assert_schedule(schedule, 0, 2, ONE_DAY, 4)

        fifth_date = fourth_date + timedelta(days=1, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, fifth_date
        )

        self.assert_schedule(schedule, 0, 2, 2 * ONE_DAY, 5)

        sixth_date = fifth_date + timedelta(days=2, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, sixth_date
        )

        self.assert_schedule(schedule, 0, 3, 0, 6)

        seventh_date = sixth_date + timedelta(days=0, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, seventh_date
        )

        self.assert_schedule(schedule, 0, 3, ONE_DAY, 7)

        eighth_date = seventh_date + timedelta(days=1, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, eighth_date
        )

        self.assert_schedule(schedule, 0, 3, 2 * ONE_DAY, 8)

        nineth_date = eighth_date + timedelta(days=2, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, nineth_date
        )

        self.assert_schedule(schedule, 0, 4, 0, 9)

        tenth_date = nineth_date + timedelta(days=0, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, tenth_date
        )

        self.assert_schedule(schedule, 0, 4, ONE_DAY, 10)

        eleventh_date = tenth_date + timedelta(days=1, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, eleventh_date
        )

        self.assert_schedule(schedule, 0, 4, 2 * ONE_DAY, 11)

        twelth_date = eleventh_date + timedelta(days=2, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, twelth_date
        )

        # Should be learned.
        assert random_bookmark.learned_time is not None

    def test_level_two_correct_exercises_in_a_day(self):
        """
        When a user does the same bookmark with a positive outcome in a day,
        the scheduler should not update.
        """

        random_bookmark = BookmarkRule(self.four_levels_user).bookmark

        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, datetime.now()
        )

        self.assert_schedule(schedule, 0, 1, ONE_DAY, 1)

        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, datetime.now()
        )

        self.assert_schedule(schedule, 0, 1, ONE_DAY, 1)

    def test_level_wrong(self):
        """
        If a user gets the bookmark wrong they should go one interval down in the
        LevelSR.
        """

        random_bookmark = BookmarkRule(self.four_levels_user).bookmark

        first_date = datetime.now()
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, first_date
        )

        self.assert_schedule(schedule, 0, 1, ONE_DAY, 1)

        second_date = first_date + timedelta(days=1, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, second_date
        )

        self.assert_schedule(schedule, 0, 1, 2 * ONE_DAY, 2)

        third_date = second_date + timedelta(days=2, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().wrong, third_date
        )

        self.assert_schedule(schedule, 0, 1, ONE_DAY, 0)

        fourth_date = third_date + timedelta(days=1, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, fourth_date
        )

        self.assert_schedule(schedule, 0, 1, 2 * ONE_DAY, 1)

    def test_level_doesnt_go_back_to_lower_level(self):
        """
        Test if when a user moves to a new level, they don't go down a level if
        they commit a mistake.
        """

        random_bookmark = BookmarkRule(self.four_levels_user).bookmark

        first_date = datetime.now()
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, first_date
        )

        self.assert_schedule(schedule, 0, 1, ONE_DAY, 1)

        second_date = first_date + timedelta(days=1, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, second_date
        )

        self.assert_schedule(schedule, 0, 1, 2 * ONE_DAY, 2)

        third_date = second_date + timedelta(days=2, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            random_bookmark, OutcomeRule().correct, third_date
        )

        self.assert_schedule(schedule, 0, 2, 0, 3)

        fourth_date = third_date + timedelta(days=0, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
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
        expected_cooling_interval,
        expected_consecutive_correct_answers,
    ):
        # tests whether the bookmark schedule is in the expected cycle, level, cooling interval, etc.
        # ML: I've switched from assert to assertEqual because otherwise my IDE was complaining that there
        # was no reason for this to be a method, because it was not using at all the reference to 'self'
        # Alternative was to extract it as a function at the top of the file, but it felt more like a method
        self.assertEqual(schedule.bookmark.learning_cycle, expected_cycle)
        self.assertEqual(schedule.bookmark.level, expected_level)
        self.assertEqual(schedule.cooling_interval, expected_cooling_interval)
        self.assertEqual(
            schedule.consecutive_correct_answers, expected_consecutive_correct_answers
        )

    def _helper_simulate_progression_up_to_productive_cycle(self, bookmark):

        first_date = datetime.now()

        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            first_date,
        )

        second_date = first_date + timedelta(days=1, seconds=1)
        print(schedule.next_practice_time, second_date)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            second_date,
        )

        third_date = second_date + timedelta(days=2, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            third_date,
        )

        fourth_date = third_date + timedelta(days=4, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            fourth_date,
        )

        fifth_date = fourth_date + timedelta(days=8, seconds=1)
        schedule = self._get_new_schedule_after_exercise(
            bookmark,
            OutcomeRule().correct,
            fifth_date,
        )
        return fifth_date, schedule

    def _get_new_schedule_after_exercise(
        self, bookmark, outcome, date: datetime = None
    ):
        exercise_session = ExerciseSessionRule(self.two_cycles_user).exerciseSession
        exercise = ExerciseRule(exercise_session, outcome, date).exercise
        bookmark.report_exercise_outcome(
            exercise.source.source,
            exercise.outcome.outcome,
            exercise.solving_speed,
            exercise_session.id,
            "",
            db_session,
            time=date,
        )

        schedule = SchedulerRule(
            bookmark.get_scheduler(), bookmark, db_session
        ).schedule
        return schedule
