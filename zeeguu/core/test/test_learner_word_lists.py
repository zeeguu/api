from datetime import datetime, timedelta
from unittest import TestCase

import zeeguu.core
from zeeguu.core.sql.learner.exercises_history import exercises_grouped_by_word
from zeeguu.core.sql.learner.words import learned_words
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.exercise_session_rule import ExerciseSessionRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.user_rule import UserRule

db_session = zeeguu.core.model.db.session


class LearnerWordListsTest(ModelTestMixIn, TestCase):
    """The teacher's Exercises tab lists: practised words and learned words.

    Both raised KeyError on any non-empty result after the UserMeaning ->
    UserWord rename, so they only ever worked for students with no data.
    """

    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.session = ExerciseSessionRule(self.user).exerciseSession
        self.when = datetime.now() - timedelta(days=1)
        self.exercise = ExerciseRule(
            self.session, OutcomeRule().too_easy, self.when
        ).exercise
        self.from_date = (self.when - timedelta(days=7)).isoformat()
        self.to_date = datetime.now().isoformat()

    def test_practised_words_grouped_with_attempts(self):
        words = exercises_grouped_by_word(
            self.user.id, None, self.from_date, self.to_date
        )

        assert len(words) == 1
        word = words[0]
        assert word["user_word_id"] == self.exercise.user_word.id
        assert word["word"] == self.exercise.user_word.meaning.origin.content
        assert [a["exercise_id"] for a in word["exerciseAttempts"]] == [
            self.exercise.id
        ]

    def test_learned_words_report_self_reported(self):
        self.exercise.user_word.learned_time = self.when
        db_session.commit()

        words = learned_words(
            self.user.id,
            self.exercise.user_word.meaning.origin.language_id,
            self.from_date,
            self.to_date,
        )

        assert len(words) == 1
        assert words[0]["word"] == self.exercise.user_word.meaning.origin.content
        assert words[0]["self_reported"] is True
