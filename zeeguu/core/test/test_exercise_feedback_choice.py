from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.model import ExerciseOutcome
from zeeguu.core.model.db import db
from zeeguu.core.model.study_choice import StudyChoice
from zeeguu.core.model.user import User
from zeeguu.core.model.user_word_interaction_history import UserWordInteractionHistory
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord

db_session = db.session


class ExerciseFeedbackChoiceTest(ModelTestMixIn):
    """
    Removing a word from practice inside an exercise reports an
    "other_feedback" outcome. Until Oct 2026 every such outcome became SKIP,
    so "I know this word" in an exercise never recorded the word as known.
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

    def _scheduled_word(self):
        user_word = BookmarkRule(self.user).bookmark.user_word
        FourLevelsPerWord.find_or_create(db_session, user_word)
        db_session.commit()
        return user_word

    def _remove_from_practice(self, user_word, feedback):
        user_word.report_exercise_outcome(
            db_session, "Recognize", ExerciseOutcome.OTHER_FEEDBACK, 0, None, feedback
        )

    def _declared_known_count(self, user_word):
        return UserWordInteractionHistory.query.filter_by(
            user_word_id=user_word.id,
            interaction_type=UserWordInteractionHistory.DECLARED_KNOWN,
        ).count()

    def test_i_know_this_records_the_word_as_known(self):
        user_word = self._scheduled_word()

        self._remove_from_practice(user_word, "i_know_this")

        assert user_word.study_choice == StudyChoice.KNOWN
        assert not user_word.fit_for_study
        assert FourLevelsPerWord.find(user_word) is None
        assert self._declared_known_count(user_word) == 1

    def test_not_worth_learning_records_a_skip(self):
        user_word = self._scheduled_word()

        self._remove_from_practice(user_word, "not_worth_learning")

        assert user_word.study_choice == StudyChoice.SKIP
        assert not user_word.fit_for_study
        assert FourLevelsPerWord.find(user_word) is None
        assert self._declared_known_count(user_word) == 0

    def test_known_after_the_edit_dialog_is_logged_once(self):
        # The edit dialog posts /dont_use_in_exercises (which logs it) and
        # then reports the exercise feedback with the same reason
        user_word = self._scheduled_word()
        user_word.choose(db_session, StudyChoice.KNOWN)
        UserWordInteractionHistory.log(
            db_session, user_word, UserWordInteractionHistory.DECLARED_KNOWN
        )
        db_session.commit()

        self._remove_from_practice(user_word, "declared_known")

        assert user_word.study_choice == StudyChoice.KNOWN
        assert self._declared_known_count(user_word) == 1
