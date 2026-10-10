"""
Fast progression, per level: every level starts on the fast track, and while a
word is on it, a clean answer (first try, no hint: outcome "C") moves it up a
level instead of waiting for three spaced correct answers. The first answer at
a level that is not clean (a hint "HC", a translation "TC", a wrong answer)
takes the word off the fast track for that level; the next level starts on it
again. So each level asks once: can you already do this?

Behind the `fast_progression` feature toggle; test_scheduling.py checks that
users without it keep the old behaviour.
See docs/future-work/exercise-selection-from-reading-evidence.md, section 5.
"""
from datetime import datetime, timedelta

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.exercise_session_rule import ExerciseSessionRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.scheduler_rule import SchedulerRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.word_scheduling import ONE_DAY

db_session = db.session

ONE_DAY_LATER = timedelta(days=1, seconds=1)
TWO_DAYS_LATER = timedelta(days=2, seconds=1)


class FastProgressionTest(ModelTestMixIn):

    @classmethod
    def setUpClass(cls):
        from zeeguu.core.test.conftest import get_shared_app, get_mock, init_fixtures_once

        cls.app = get_shared_app()
        get_mock()

        with cls.app.app_context():
            init_fixtures_once()

            fast_user = UserRule().user
            fast_user.is_dev = True   # the toggle starts out on for dev accounts
            db_session.add(fast_user)
            db_session.commit()
            cls._fast_user_id = fast_user.id
            cls._normal_user_id = UserRule().user.id

    @classmethod
    def tearDownClass(cls):
        from zeeguu.core.test.conftest import cleanup_tables

        with cls.app.app_context():
            db_session.close()
            cleanup_tables()

    def setUp(self):
        self.fast_user = User.find_by_id(self._fast_user_id)
        self.normal_user = User.find_by_id(self._normal_user_id)

    def tearDown(self):
        pass   # tables are cleaned once, in tearDownClass; the mixin would do it per test

    def run(self, result=None):
        with self.app.app_context():
            super(ModelTestMixIn, self).run(result)

    def test_toggle_is_on_only_for_the_fast_user(self):
        self.assertTrue(self.fast_user.has_feature("fast_progression"))
        self.assertFalse(self.normal_user.has_feature("fast_progression"))

    def test_clean_answer_moves_up_a_level_and_comes_back_tomorrow(self):
        bookmark = BookmarkRule(self.fast_user).bookmark
        now = datetime.now()

        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct, now)

        self.assertEqual(schedule.user_word.level, 2)
        self.assertEqual(schedule.cooling_interval, 0)   # at the start of the new level
        self.assertGreaterEqual(schedule.next_practice_time, now + timedelta(days=1))

    def test_after_a_fast_level_up_answers_with_a_hint_need_all_three_steps(self):
        bookmark = BookmarkRule(self.fast_user).bookmark
        day = datetime.now()

        self._answer(self.fast_user, bookmark, OutcomeRule().correct, day)   # level 1 -> 2

        day += ONE_DAY_LATER
        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct_after_hint, day)
        self.assertEqual((schedule.user_word.level, schedule.cooling_interval), (2, ONE_DAY))

        day += ONE_DAY_LATER
        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct_after_hint, day)
        self.assertEqual((schedule.user_word.level, schedule.cooling_interval), (2, 2 * ONE_DAY))

        day += TWO_DAYS_LATER
        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct_after_hint, day)
        self.assertEqual(schedule.user_word.level, 3)

    def test_answer_with_a_hint_keeps_todays_rules(self):
        bookmark = BookmarkRule(self.fast_user).bookmark

        schedule = self._answer(
            self.fast_user, bookmark, OutcomeRule().correct_after_hint, datetime.now()
        )

        # same as a correct answer today: still level 1, next interval one day
        self.assertEqual(schedule.user_word.level, 1)
        self.assertEqual(schedule.cooling_interval, ONE_DAY)

    def test_a_wrong_answer_after_moving_up_does_not_drop_the_word_back(self):
        # the clean answer at level 1 still stands; the failure is about level 2,
        # so the word restarts level 2 at step 0, as after any level-up
        bookmark = BookmarkRule(self.fast_user).bookmark
        day = datetime.now()

        self._answer(self.fast_user, bookmark, OutcomeRule().correct, day)   # level 1 -> 2
        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().wrong, day + ONE_DAY_LATER)

        self.assertEqual(schedule.user_word.level, 2)
        self.assertEqual(schedule.cooling_interval, 0)

    def test_finishing_an_audio_lesson_is_not_a_clean_answer(self):
        # an audio lesson reports "Listened" for each of its words: nobody answered,
        # so it schedules like today's correct answer and never fast-forwards
        bookmark = BookmarkRule(self.fast_user).bookmark

        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().listened, datetime.now())

        self.assertEqual(schedule.user_word.level, 1)
        self.assertEqual(schedule.cooling_interval, ONE_DAY)

    def test_known_word_is_learned_after_four_clean_answers_on_four_days(self):
        bookmark = BookmarkRule(self.fast_user).bookmark
        day = datetime.now()

        for expected_level in (2, 3, 4):
            schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct, day)
            self.assertEqual(schedule.user_word.level, expected_level)
            self.assertIsNone(bookmark.user_word.learned_time)
            day += ONE_DAY_LATER

        # the fourth clean answer, a day after reaching level 4
        self._answer(self.fast_user, bookmark, OutcomeRule().correct, day)
        self.assertIsNotNone(bookmark.user_word.learned_time)

    def test_two_clean_answers_on_the_same_day_count_once(self):
        # spacing is kept: answering again before the word is due changes nothing
        bookmark = BookmarkRule(self.fast_user).bookmark
        # fixed morning time: "+1 hour" must stay on the same calendar day
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

        self._answer(self.fast_user, bookmark, OutcomeRule().correct, now)
        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct,
                                now + timedelta(hours=1))

        self.assertEqual(schedule.user_word.level, 2)

    def test_without_the_toggle_a_clean_answer_keeps_todays_rules(self):
        bookmark = BookmarkRule(self.normal_user).bookmark

        schedule = self._answer(self.normal_user, bookmark, OutcomeRule().correct, datetime.now())

        self.assertEqual(schedule.user_word.level, 1)
        self.assertEqual(schedule.cooling_interval, ONE_DAY)

    # ---- the fast track is per level -------------------------------------------

    def test_after_a_hint_a_clean_answer_at_the_same_level_is_only_a_step(self):
        bookmark = BookmarkRule(self.fast_user).bookmark
        day = datetime.now()

        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct_after_hint, day)
        self.assertFalse(schedule.fast_track)

        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct, day + ONE_DAY_LATER)
        self.assertEqual((schedule.user_word.level, schedule.cooling_interval), (1, 2 * ONE_DAY))

    def test_after_a_wrong_answer_a_clean_answer_at_the_same_level_is_only_a_step(self):
        bookmark = BookmarkRule(self.fast_user).bookmark
        day = datetime.now()

        self._answer(self.fast_user, bookmark, OutcomeRule().correct, day)   # level 1 -> 2
        day += ONE_DAY_LATER
        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().wrong, day)
        self.assertFalse(schedule.fast_track)

        day += ONE_DAY_LATER
        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct, day)
        self.assertEqual((schedule.user_word.level, schedule.cooling_interval), (2, ONE_DAY))

    def test_the_next_level_starts_on_the_fast_track_again(self):
        # level 1 the slow way (a hint, then three correct answers), then level 2
        # opens with a clean answer and moves up at once
        bookmark = BookmarkRule(self.fast_user).bookmark
        day = datetime.now()

        self._answer(self.fast_user, bookmark, OutcomeRule().correct_after_hint, day)  # step 1
        day += ONE_DAY_LATER
        self._answer(self.fast_user, bookmark, OutcomeRule().correct, day)             # step 2
        day += TWO_DAYS_LATER
        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct, day)  # level 2
        self.assertEqual(schedule.user_word.level, 2)
        self.assertTrue(schedule.fast_track)

        day += ONE_DAY_LATER
        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct, day)
        self.assertEqual(schedule.user_word.level, 3)

    def test_an_audio_lesson_does_not_take_the_word_off_the_fast_track(self):
        # "Listened" is not an answer, so it is not a stumble either
        bookmark = BookmarkRule(self.fast_user).bookmark
        day = datetime.now()

        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().listened, day)
        self.assertTrue(schedule.fast_track)

        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct, day + ONE_DAY_LATER)
        self.assertEqual(schedule.user_word.level, 2)

    def test_the_fast_track_is_recorded_for_users_without_the_toggle_too(self):
        # so the comparison group shows which words would have stayed on it
        bookmark = BookmarkRule(self.normal_user).bookmark

        schedule = self._answer(self.normal_user, bookmark, OutcomeRule().wrong, datetime.now())

        self.assertFalse(schedule.fast_track)
        self.assertFalse(schedule.is_on_fast_track())   # the column, and the toggle

    def test_is_on_fast_track_needs_both_the_column_and_the_toggle(self):
        bookmark = BookmarkRule(self.fast_user).bookmark

        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct, datetime.now())
        self.assertTrue(schedule.is_on_fast_track())

        normal_bookmark = BookmarkRule(self.normal_user).bookmark
        normal_schedule = self._answer(self.normal_user, normal_bookmark, OutcomeRule().correct,
                                       datetime.now())
        self.assertTrue(normal_schedule.fast_track)
        self.assertFalse(normal_schedule.is_on_fast_track())

    def test_the_api_tells_the_frontend_whether_the_word_is_on_the_fast_track(self):
        # the level bar and the "learned" check read this, not the user's features
        bookmark = BookmarkRule(self.fast_user).bookmark
        bookmark.user_word.preferred_bookmark = bookmark   # as for any word in production
        day = datetime.now()

        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().correct, day)
        info = bookmark.user_word.as_dictionary(schedule=schedule, with_context_tokenized=False)
        self.assertIs(info["fast_track"], True)

        schedule = self._answer(self.fast_user, bookmark, OutcomeRule().wrong, day + ONE_DAY_LATER)
        info = bookmark.user_word.as_dictionary(schedule=schedule, with_context_tokenized=False)
        self.assertIs(info["fast_track"], False)

    def _answer(self, user, bookmark, outcome, date):
        exercise_session = ExerciseSessionRule(user).exerciseSession
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
        return SchedulerRule(
            bookmark.user_word.get_scheduler(), bookmark.user_word, db_session
        ).schedule
