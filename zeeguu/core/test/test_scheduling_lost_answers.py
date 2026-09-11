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
    Two ways the scheduler used to lose a learner's exercise answer. Both ended
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
        # report_exercise_outcome adds the learner's Exercise row before it calls
        # the scheduler. Rolling the whole session back to recover would discard
        # it -- the answer lost, not merely left unscheduled -- and the endpoint
        # would answer FAIL. A bystander insert stands in for that Exercise.
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
