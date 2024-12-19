from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.exercise_session_rule import ExerciseSessionRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.scheduler_rule import SchedulerRule
from zeeguu.core.word_scheduling.basicSR.basicSR import ONE_DAY
from zeeguu.core.model import db
from datetime import datetime, timedelta

db_session = db.session


class SchedulerTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        # Cycles is on by default.
        self.user_rule_cycle = UserRule()
        self.user_l_cycle = self.user_rule_cycle.user
        self.user_rule_levels = UserRule()
        self.user_levels = self.user_rule_levels.user
        self.user_levels.invitation_code = "exercise_levels"
        db_session.add(self.user_levels)
        db_session.commit()

    def _helper_assert_bookmark_schedule(
        self,
        bookmark,
        schedule,
        expected_cycle,
        expected_level,
        expected_cooling_interval,
        expected_consecutive_correct_answers,
    ):

        assert bookmark.learning_cycle == expected_cycle
        assert bookmark.level == expected_level
        assert schedule.cooling_interval == expected_cooling_interval
        assert (
            schedule.consecutive_correct_answers == expected_consecutive_correct_answers
        )

    def _helper_simulate_progression_up_to_productive_cycle(self, bookmark):
        from zeeguu.core.word_scheduling.basicSR.learning_cycle_SR import (
            LearningCyclesSR,
        )

        first_date = datetime.now()

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            first_date,
        )

        second_date = first_date + timedelta(days=1, seconds=1)
        print(schedule.next_practice_time, second_date)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            second_date,
        )

        third_date = second_date + timedelta(days=2, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            third_date,
        )

        fourth_date = third_date + timedelta(days=4, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            fourth_date,
        )

        fifth_date = fourth_date + timedelta(days=8, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            fifth_date,
        )
        return fifth_date, schedule

    def _helper_create_exercise_for_bookmark_and_get_schedule(
        self, bookmark, outcome, scheduler_model, date: datetime = None
    ):
        exercise_session = ExerciseSessionRule(self.user_l_cycle).exerciseSession
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

        schedule = SchedulerRule(scheduler_model, bookmark, db_session).schedule
        return schedule

    def test_learning_cycle_schedule_is_created(self):
        from zeeguu.core.word_scheduling.basicSR.learning_cycle_SR import (
            LearningCyclesSR,
        )

        random_bookmark = BookmarkRule(self.user_l_cycle).bookmark

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LearningCyclesSR, datetime.now()
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, ONE_DAY, 1
        )

        random_bookmark_2 = BookmarkRule(self.user_l_cycle).bookmark

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark_2, OutcomeRule().wrong, LearningCyclesSR, datetime.now()
        )

        self._helper_assert_bookmark_schedule(random_bookmark_2, schedule, 1, 0, 0, 0)

    def test_learning_cycle_two_correct_exercises_in_a_day(self):
        from zeeguu.core.word_scheduling.basicSR.learning_cycle_SR import (
            LearningCyclesSR,
        )

        """
            When a user does the same bookmark with a positive outcome in a day,
            the scheduler should not update.
        """

        random_bookmark = BookmarkRule(self.user_l_cycle).bookmark

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LearningCyclesSR, datetime.now()
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, ONE_DAY, 1
        )

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LearningCyclesSR, datetime.now()
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, ONE_DAY, 1
        )

    def test_learning_cycle_full_cycle(self):

        from zeeguu.core.word_scheduling.basicSR.learning_cycle_SR import (
            LearningCyclesSR,
        )

        """
            Tests the entire learning cycle process, all the values are hardset
            to ensure they match the expectation.

        """

        random_bookmark = BookmarkRule(self.user_l_cycle).bookmark
        first_date = datetime.now()

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            first_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, ONE_DAY, 1
        )

        second_date = first_date + timedelta(days=1, seconds=1)

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            second_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, 2 * ONE_DAY, 2
        )

        third_date = second_date + timedelta(days=2, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            third_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, 4 * ONE_DAY, 3
        )

        fourth_date = third_date + timedelta(days=4, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            fourth_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, 8 * ONE_DAY, 4
        )

        fifth_date = fourth_date + timedelta(days=8, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            fifth_date,
        )

        self._helper_assert_bookmark_schedule(random_bookmark, schedule, 2, 0, 0, 5)

        six_date = fifth_date + timedelta(days=0, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            six_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 2, 0, ONE_DAY, 6
        )

        seven_date = six_date + timedelta(days=1, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            seven_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 2, 0, 2 * ONE_DAY, 7
        )

        eight_date = seven_date + timedelta(days=2, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            eight_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 2, 0, 4 * ONE_DAY, 8
        )

        nine_date = eight_date + timedelta(days=4, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            nine_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 2, 0, 8 * ONE_DAY, 9
        )

        ten_date = nine_date + timedelta(days=8, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            ten_date,
        )

        assert random_bookmark.learned_time != None

    def test_learning_cycle_wrong(self):

        from zeeguu.core.word_scheduling.basicSR.learning_cycle_SR import (
            LearningCyclesSR,
        )

        """
            Test the scheduler when the user gets an error.
            The schedule should go back one interval, and not reset completely.
        """

        random_bookmark = BookmarkRule(self.user_l_cycle).bookmark
        first_date = datetime.now()

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            first_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, ONE_DAY, 1
        )

        second_date = first_date + timedelta(days=1, seconds=1)
        print(schedule.next_practice_time, second_date)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().wrong,
            LearningCyclesSR,
            second_date,
        )

        self._helper_assert_bookmark_schedule(random_bookmark, schedule, 1, 0, 0, 0)

        third_date = second_date + timedelta(days=0, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            third_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, ONE_DAY, 1
        )

        fourth_date = third_date + timedelta(days=1, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().correct,
            LearningCyclesSR,
            fourth_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, 2 * ONE_DAY, 2
        )

        fifth_date = fourth_date + timedelta(days=2, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().wrong,
            LearningCyclesSR,
            fifth_date,
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 1, 0, ONE_DAY, 0
        )

    def test_learning_cycle_productive_doesnt_go_down_to_receptive(self):
        """
        A bookmark shouldn't go down a cycle, meaning if we get to
        productive then the bookmark doesn't go back to receptive.
        """
        from zeeguu.core.word_scheduling.basicSR.learning_cycle_SR import (
            LearningCyclesSR,
        )

        random_bookmark = BookmarkRule(self.user_l_cycle).bookmark
        last_date, schedule = self._helper_simulate_progression_up_to_productive_cycle(
            random_bookmark
        )
        assert schedule.consecutive_correct_answers == 5
        assert schedule.cooling_interval == 0

        fifth_date = last_date + timedelta(days=0, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark,
            OutcomeRule().wrong,
            LearningCyclesSR,
            fifth_date,
        )

        assert random_bookmark.learning_cycle == 2
        assert schedule.consecutive_correct_answers == 0
        assert schedule.cooling_interval == 0

    def test_level_schedule_is_created(self):
        """
        Testing if LevelsSR creates the schedule once the bookmark is practiced.
        """
        from zeeguu.core.word_scheduling.basicSR.levels_SR import LevelsSR

        random_bookmark = BookmarkRule(self.user_levels).bookmark

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, datetime.now()
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, ONE_DAY, 1
        )

        random_bookmark_2 = BookmarkRule(self.user_levels).bookmark

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark_2, OutcomeRule().wrong, LevelsSR, datetime.now()
        )

        self._helper_assert_bookmark_schedule(random_bookmark_2, schedule, 0, 1, 0, 0)

    def test_level_full_cycle(self):
        """
        Test the full progression through all the 4 levels with 2 intervals each.
        All values are hardset and asserted to ensure we catch any changes to the
        scheduler.
        """
        from zeeguu.core.word_scheduling.basicSR.levels_SR import LevelsSR

        random_bookmark = BookmarkRule(self.user_levels).bookmark

        first_date = datetime.now()
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, first_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, ONE_DAY, 1
        )

        second_date = first_date + timedelta(days=1, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, second_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, 2 * ONE_DAY, 2
        )

        third_date = second_date + timedelta(days=2, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, third_date
        )

        self._helper_assert_bookmark_schedule(random_bookmark, schedule, 0, 2, 0, 3)

        fourth_date = third_date + timedelta(days=0, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, fourth_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 2, ONE_DAY, 4
        )

        fifth_date = fourth_date + timedelta(days=1, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, fifth_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 2, 2 * ONE_DAY, 5
        )

        sixth_date = fifth_date + timedelta(days=2, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, sixth_date
        )

        self._helper_assert_bookmark_schedule(random_bookmark, schedule, 0, 3, 0, 6)

        seventh_date = sixth_date + timedelta(days=0, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, seventh_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 3, ONE_DAY, 7
        )

        eighth_date = seventh_date + timedelta(days=1, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, eighth_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 3, 2 * ONE_DAY, 8
        )

        nineth_date = eighth_date + timedelta(days=2, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, nineth_date
        )

        self._helper_assert_bookmark_schedule(random_bookmark, schedule, 0, 4, 0, 9)

        tenth_date = nineth_date + timedelta(days=0, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, tenth_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 4, ONE_DAY, 10
        )

        eleventh_date = tenth_date + timedelta(days=1, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, eleventh_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 4, 2 * ONE_DAY, 11
        )

        twelth_date = eleventh_date + timedelta(days=2, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, twelth_date
        )

        # Should be learned.
        assert random_bookmark.learned_time is not None

    def test_level_two_correct_exercises_in_a_day(self):
        """
        When a user does the same bookmark with a positive outcome in a day,
        the scheduler should not update.
        """
        from zeeguu.core.word_scheduling.basicSR.levels_SR import LevelsSR

        random_bookmark = BookmarkRule(self.user_levels).bookmark

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, datetime.now()
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, ONE_DAY, 1
        )

        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, datetime.now()
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, ONE_DAY, 1
        )

    def test_level_wrong(self):
        """
        If a user gets the bookmark wrong they should go one interval down in the
        LevelSR.
        """
        from zeeguu.core.word_scheduling.basicSR.levels_SR import LevelsSR

        random_bookmark = BookmarkRule(self.user_levels).bookmark

        first_date = datetime.now()
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, first_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, ONE_DAY, 1
        )

        second_date = first_date + timedelta(days=1, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, second_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, 2 * ONE_DAY, 2
        )

        third_date = second_date + timedelta(days=2, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().wrong, LevelsSR, third_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, ONE_DAY, 0
        )

        fourth_date = third_date + timedelta(days=1, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, fourth_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, 2 * ONE_DAY, 1
        )

    def test_level_doesnt_go_back_to_lower_level(self):
        """
        Test if when a user moves to a new level, they don't go down a level if
        they commit a mistake.
        """
        from zeeguu.core.word_scheduling.basicSR.levels_SR import LevelsSR

        random_bookmark = BookmarkRule(self.user_levels).bookmark

        first_date = datetime.now()
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, first_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, ONE_DAY, 1
        )

        second_date = first_date + timedelta(days=1, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, second_date
        )

        self._helper_assert_bookmark_schedule(
            random_bookmark, schedule, 0, 1, 2 * ONE_DAY, 2
        )

        third_date = second_date + timedelta(days=2, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().correct, LevelsSR, third_date
        )

        self._helper_assert_bookmark_schedule(random_bookmark, schedule, 0, 2, 0, 3)

        fourth_date = third_date + timedelta(days=0, seconds=1)
        schedule = self._helper_create_exercise_for_bookmark_and_get_schedule(
            random_bookmark, OutcomeRule().wrong, LevelsSR, fourth_date
        )

        self._helper_assert_bookmark_schedule(random_bookmark, schedule, 0, 2, 0, 0)
