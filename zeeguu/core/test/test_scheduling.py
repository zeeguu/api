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

    # ================================================================================================================
    # Regression tests for the SR exercise-outcome failures in the 2026-07-15 log digest
    # ================================================================================================================

    def test_update_returns_user_word_when_scheduler_declines(self):
        """
        find_or_create() returns None when a word is judged unfit for study
        (invalid / duplicate / unvalidatable translation). update() must not
        dereference that None ('NoneType' has no attribute 'update_schedule')
        and must return the passed-in user_word.
        """
        from unittest.mock import patch
        from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

        bookmark = BookmarkRule(self.four_levels_user).bookmark
        user_word = bookmark.user_word
        scheduler = user_word.get_scheduler()

        with patch.object(scheduler, "find_or_create", return_value=None):
            result = scheduler.update(
                db_session, user_word, OutcomeRule().correct.outcome, datetime.now()
            )

        assert result is user_word
        # nothing should have been scheduled
        assert BasicSRSchedule.find_by_user_word(user_word) is None

    def test_report_outcome_logs_exercise_against_surviving_word(self):
        """
        A scheduler can replace the practiced UserWord with a corrected one and
        delete the original (as the validation re-home does). report_exercise_outcome
        must log the Exercise against the survivor scheduler.update() returns, not
        the deleted original (which raised 'Instance UserWord has been deleted').
        """
        from unittest.mock import patch
        from zeeguu.core.model.exercise import Exercise
        from zeeguu.core.model.user_word import UserWord
        from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import (
            FourLevelsPerWord,
        )

        old_bookmark = BookmarkRule(self.four_levels_user).bookmark
        old_user_word = old_bookmark.user_word

        new_bookmark = BookmarkRule(self.four_levels_user).bookmark
        new_user_word = new_bookmark.user_word
        db_session.commit()
        new_user_word_id = new_user_word.id
        old_user_word_id = old_user_word.id

        def fake_update(db_sess, user_word, outcome, time=None):
            # Simulate a scheduler that re-homes the word: delete the original,
            # return the survivor (mirrors validate_and_fix's re-home).
            db_sess.delete(user_word)
            db_sess.commit()
            return UserWord.query.get(new_user_word_id)

        with patch.object(FourLevelsPerWord, "update", side_effect=fake_update):
            # Must not raise "Instance UserWord has been deleted"
            old_user_word.report_exercise_outcome(
                db_session,
                "Recognize",
                OutcomeRule().correct.outcome,
                1000,
                None,
                "",
            )

        # the original was deleted, the exercise is logged against the survivor
        assert UserWord.query.get(old_user_word_id) is None
        logged = Exercise.query.filter_by(user_word_id=new_user_word_id).all()
        assert len(logged) == 1
        assert (
            Exercise.query.filter_by(user_word_id=old_user_word_id).count() == 0
        )

    def test_find_or_create_recovers_from_duplicate_schedule_race(self):
        """
        Two concurrent requests can both pass the "no schedule yet" check and
        try to insert. The unique_user_word_schedule constraint makes the loser's
        commit raise IntegrityError; find_or_create must roll back and return the
        row the winner created instead of surfacing a 500.
        """
        from unittest.mock import patch
        from zeeguu.core.model.meaning import Meaning
        from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
        from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import (
            FourLevelsPerWord,
        )

        bookmark = BookmarkRule(self.four_levels_user).bookmark
        user_word = bookmark.user_word
        user_word.meaning.validated = Meaning.VALID  # skip validation branch
        db_session.add(user_word.meaning)
        db_session.commit()

        # The "winner" row that a concurrent request already committed.
        winner = FourLevelsPerWord(user_word=user_word)
        db_session.add(winner)
        db_session.commit()
        winner_id = winner.id

        # Force the create path — as if our SELECT ran before the winner
        # committed — so find() returns None first and then the winner on the
        # post-rollback re-fetch. The real unique_user_word_schedule constraint
        # then fires on our duplicate insert; find_or_create must roll back and
        # return the winner's row instead of surfacing a 500.
        with patch.object(BasicSRSchedule, "find", side_effect=[None, winner]):
            result = FourLevelsPerWord.find_or_create(db_session, user_word)

        assert result is not None
        assert result.id == winner_id
        assert (
            BasicSRSchedule.query.filter_by(user_word_id=user_word.id).count() == 1
        )

    # ================================================================================================================
    # Off-hot-path (async + nightly) translation validation
    # ================================================================================================================

    def test_find_or_create_does_not_validate_inline(self):
        """
        Scheduling must no longer call the LLM validator on the hot path — an
        unvalidated word is scheduled as-is, validation happens off-path.
        """
        from unittest.mock import patch
        from zeeguu.core.model.meaning import Meaning
        from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
        from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import (
            FourLevelsPerWord,
        )
        from zeeguu.core.llm_services.validation_service import (
            UserWordValidationService,
        )

        bookmark = BookmarkRule(self.four_levels_user).bookmark
        user_word = bookmark.user_word
        user_word.meaning.validated = Meaning.NOT_VALIDATED
        db_session.add(user_word.meaning)
        db_session.commit()

        with patch.object(
            UserWordValidationService, "validate_and_fix"
        ) as vf, patch.object(
            UserWordValidationService, "check_for_duplicate_meaning"
        ) as dup:
            schedule = FourLevelsPerWord.find_or_create(db_session, user_word)

        vf.assert_not_called()
        dup.assert_not_called()
        assert schedule is not None
        assert BasicSRSchedule.find_by_user_word(user_word) is not None

    def test_validate_scheduled_user_word_is_noop_when_already_valid(self):
        """The worker is idempotent: a VALID meaning does no validation work."""
        from unittest.mock import patch
        from zeeguu.core.model.meaning import Meaning
        from zeeguu.core.llm_services.validation_service import (
            UserWordValidationService,
        )

        bookmark = BookmarkRule(self.four_levels_user).bookmark
        user_word = bookmark.user_word
        user_word.meaning.validated = Meaning.VALID
        db_session.add(user_word.meaning)
        db_session.commit()

        with patch.object(UserWordValidationService, "validate_and_fix") as vf:
            UserWordValidationService.validate_scheduled_user_word(user_word.id)

        vf.assert_not_called()

    def test_validate_scheduled_user_word_unfit_leaves_rotation(self):
        """
        When validation deems the word unfit (validate_and_fix -> None), the
        worker drops it from the schedule so a known-bad word stops appearing.
        """
        from unittest.mock import patch
        from zeeguu.core.model.meaning import Meaning
        from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
        from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import (
            FourLevelsPerWord,
        )
        from zeeguu.core.llm_services.validation_service import (
            UserWordValidationService,
        )

        bookmark = BookmarkRule(self.four_levels_user).bookmark
        user_word = bookmark.user_word
        user_word.meaning.validated = Meaning.NOT_VALIDATED
        schedule = FourLevelsPerWord(user_word=user_word)
        db_session.add_all([user_word.meaning, schedule])
        db_session.commit()
        uw_id = user_word.id
        assert BasicSRSchedule.find_by_user_word(user_word) is not None

        with patch.object(
            UserWordValidationService, "validate_and_fix", return_value=None
        ):
            UserWordValidationService.validate_scheduled_user_word(uw_id)

        assert BasicSRSchedule.query.filter_by(user_word_id=uw_id).count() == 0

    def test_off_hot_path_validation_fires_only_for_scheduled_unvalidated_word(self):
        """
        The trigger implements the pipeline compromise: fire background validation
        for a scheduled, not-yet-valid word; skip it when the word isn't scheduled
        (full pipeline → left for the nightly batch).
        """
        from unittest.mock import patch
        from zeeguu.core.model.meaning import Meaning
        from zeeguu.core.model.user_word import UserWord
        from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import (
            FourLevelsPerWord,
        )
        from zeeguu.core.llm_services.validation_service import (
            UserWordValidationService,
        )

        # Scheduled + unvalidated → fires
        scheduled_bm = BookmarkRule(self.four_levels_user).bookmark
        scheduled_uw = scheduled_bm.user_word
        scheduled_uw.meaning.validated = Meaning.NOT_VALIDATED
        db_session.add_all(
            [scheduled_uw.meaning, FourLevelsPerWord(user_word=scheduled_uw)]
        )

        # Unscheduled + unvalidated → does NOT fire (nightly handles it)
        unscheduled_bm = BookmarkRule(self.four_levels_user).bookmark
        unscheduled_uw = unscheduled_bm.user_word
        unscheduled_uw.meaning.validated = Meaning.NOT_VALIDATED
        db_session.add(unscheduled_uw.meaning)
        db_session.commit()

        self.app.config["TESTING"] = False
        try:
            with patch(
                "zeeguu.api.utils.background.run_in_background"
            ) as run_bg:
                UserWord._maybe_validate_off_hot_path(scheduled_uw)
                assert run_bg.call_count == 1
                assert (
                    run_bg.call_args.args[0]
                    == UserWordValidationService.validate_scheduled_user_word
                )
                assert run_bg.call_args.args[1] == scheduled_uw.id

                run_bg.reset_mock()
                UserWord._maybe_validate_off_hot_path(unscheduled_uw)
                run_bg.assert_not_called()
        finally:
            self.app.config["TESTING"] = True
