from contextlib import contextmanager
from unittest.mock import patch

import sqlalchemy

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.model.user import User
from zeeguu.core.model.db import db
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord

db_session = db.session


class SchedulingLostAnswersTest(ModelTestMixIn):
    """
    Ways the scheduler used to lose a learner's exercise answer. Each ended
    the same way: an exception out of the scheduler, into the catch-all in
    /report_exercise_outcome, answered as "FAIL", with the pending Exercise row
    rolled back.

    basic_sr_schedule has UNIQUE (user_word_id). Two requests scheduling the same
    word both find nothing and both insert; one of them loses.

    It is not a narrow window: find_or_create validates the translation through
    the LLM before it inserts, so seconds pass between the find and the insert.
    """

    @classmethod
    def setUpClass(cls):
        from zeeguu.core.test.conftest import get_shared_app, get_mock, init_fixtures_once

        cls.app = get_shared_app()
        get_mock()

        with cls.app.app_context():
            init_fixtures_once()
            cls.user_rule = UserRule()
            cls._user_id = cls.user_rule.user.id

    @classmethod
    def tearDownClass(cls):
        from zeeguu.core.test.conftest import cleanup_tables

        with cls.app.app_context():
            db_session.close()
            cleanup_tables()

    def setUp(self):
        self.user = User.find_by_id(self._user_id)

    def tearDown(self):
        pass

    def run(self, result=None):
        with self.app.app_context():
            super(ModelTestMixIn, self).run(result)

    @contextmanager
    def _the_winner_arrives_during_validation(self):
        """
        find() empty while the row exists is exactly what the loser sees: the
        winner committed while this request was still inside the LLM validation.
        The second call is find_or_create's recovery, which must see the truth.
        """
        real_find = BasicSRSchedule.find
        calls = []

        def flaky_find(cls, user_word):
            calls.append(user_word)
            if len(calls) == 1:
                return None
            return real_find(user_word)

        with patch.object(BasicSRSchedule, "find", classmethod(flaky_find)):
            yield

    def test_losing_the_race_returns_the_winners_schedule(self):
        user_word = BookmarkRule(self.user).bookmark.user_word
        winner = FourLevelsPerWord.find_or_create(db_session, user_word)
        assert winner is not None

        with self._the_winner_arrives_during_validation():
            recovered = FourLevelsPerWord.find_or_create(db_session, user_word)

        assert recovered is not None, "the loser got nothing back"
        assert recovered.id == winner.id

    def test_losing_the_race_leaves_exactly_one_schedule(self):
        user_word = BookmarkRule(self.user).bookmark.user_word
        FourLevelsPerWord.find_or_create(db_session, user_word)

        with self._the_winner_arrives_during_validation():
            FourLevelsPerWord.find_or_create(db_session, user_word)
        db_session.commit()

        assert (
            BasicSRSchedule.query.filter_by(user_word_id=user_word.id).count() == 1
        )

    def test_losing_the_race_keeps_the_callers_pending_work(self):
        # A caller can have its own pending work in the session (the learner's
        # Exercise, when report_exercise_outcome added it before scheduling).
        # Rolling the whole session back to recover would discard it. A
        # bystander insert stands in for that work.
        user_word = BookmarkRule(self.user).bookmark.user_word
        FourLevelsPerWord.find_or_create(db_session, user_word)

        bystander_word = BookmarkRule(self.user).bookmark.user_word
        db_session.add(FourLevelsPerWord(bystander_word))

        with self._the_winner_arrives_during_validation():
            FourLevelsPerWord.find_or_create(db_session, user_word)

        db_session.commit()
        assert (
            BasicSRSchedule.query.filter_by(user_word_id=bystander_word.id).count() == 1
        ), "the caller's pending row was rolled back with the failed insert"

    def test_a_word_the_scheduler_declines_does_not_lose_the_answer(self):
        """
        find_or_create returns None for a word whose translation failed
        validation, that is unfit for study, or that duplicates a meaning already
        being learned. update() went straight on to schedule.update_schedule(),
        which is an AttributeError on None -- and the learner's answer went down
        with it.
        """
        from zeeguu.core.model.exercise_outcome import ExerciseOutcome

        user_word = BookmarkRule(self.user).bookmark.user_word

        with patch.object(
            FourLevelsPerWord, "find_or_create", classmethod(lambda cls, s, uw: None)
        ):
            FourLevelsPerWord.update(db_session, user_word, ExerciseOutcome.CORRECT)

        # Nothing scheduled, which is the point -- and no exception, so the
        # caller still commits the exercise.
        assert BasicSRSchedule.query.filter_by(user_word_id=user_word.id).count() == 0

    def test_the_answer_survives_validation_replacing_the_word(self):
        """
        Scheduling a word for the first time validates its translation through
        the LLM. When the LLM corrects it, validation moves the learner's bookmark
        to a UserWord for the corrected meaning and deletes the original. The
        answer used to be bound to that original before scheduling ran, so the
        commit failed with "Instance <UserWord> has been deleted" and the answer
        was lost (7 times in 9 days in production, Sep 2026).
        """
        from zeeguu.core.bookmark_operations.update_bookmark import cleanup_old_user_word
        from zeeguu.core.llm_services.validation_service import UserWordValidationService
        from zeeguu.core.model.exercise import Exercise
        from zeeguu.core.model.exercise_outcome import ExerciseOutcome
        from zeeguu.core.model.user_word import UserWord

        bookmark = BookmarkRule(self.user).bookmark
        original = bookmark.user_word
        original_id = original.id
        # Validation only runs through the word's preferred bookmark.
        original.preferred_bookmark_id = bookmark.id
        db_session.add(original)
        db_session.commit()
        replacement = BookmarkRule(self.user).bookmark.user_word

        def corrects_the_translation(cls, session, user_word):
            # What _fix_bookmark does when the meaning changes.
            bookmark.user_word_id = replacement.id
            session.add(bookmark)
            session.flush()
            replacement.preferred_bookmark_id = bookmark.id
            session.add(replacement)
            cleanup_old_user_word(session, user_word, bookmark)
            session.commit()
            return replacement

        with patch.object(
            UserWordValidationService, "validate_and_fix", classmethod(corrects_the_translation)
        ):
            original.report_exercise_outcome(
                db_session, "Recognize", ExerciseOutcome.CORRECT, 1000, None, ""
            )

        assert UserWord.query.get(original_id) is None, "validation should have replaced the word"
        answers = Exercise.query.filter_by(user_word_id=replacement.id).all()
        assert len(answers) == 1, "the learner's answer was lost"
