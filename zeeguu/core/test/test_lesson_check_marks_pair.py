"""When the lesson check finds the word/translation pair itself wrong, the
meaning is marked INVALID, and the mark outlives the caller's rollback."""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.audio_lessons import daily_lesson_generator
from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator
from zeeguu.core.audio_lessons.script_generator import LessonNotCorrect
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.validation_log import ValidationAction, ValidationLog
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session

WRONG_PAIR = [{"line": 4, "text": "Teacher: experienced.", "kind": "translation", "issue": "connu is 'known'"}]
WRONG_LINE = [{"line": 9, "text": "Man: x", "kind": "sense", "issue": "wrong sense"}]


class LessonCheckMarksPairTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user_word = BookmarkRule(UserRule().user).bookmark.user_word
        self.meaning = self.user_word.meaning
        self.meaning.validated = Meaning.VALID
        session.add(self.meaning)
        session.commit()

    def _generate_refused_with(self, problems):
        def refuse(**kwargs):
            raise LessonNotCorrect("refused", problems)

        generator = DailyLessonGenerator.__new__(DailyLessonGenerator)
        with patch.object(daily_lesson_generator, "generate_lesson_script", refuse):
            with self.assertRaises(LessonNotCorrect):
                generator.generate_audio_lesson_meaning(
                    self.user_word, "da", "en", "A1", voice_variety=None
                )
        session.rollback()  # what the callers do
        session.expire_all()
        return session.get(Meaning, self.meaning.id)

    def test_a_wrong_pair_marks_the_meaning_invalid_and_logs_why(self):
        meaning = self._generate_refused_with(WRONG_PAIR)
        self.assertEqual(meaning.validated, Meaning.INVALID)
        logged = ValidationLog.query.filter_by(meaning_id=meaning.id).one()
        self.assertEqual(logged.action, ValidationAction.INVALID)
        self.assertEqual(logged.reason, "[audio lesson check] connu is 'known'")
        self.assertEqual(logged.user_word_id, self.user_word.id)

    def test_a_wrong_script_leaves_the_meaning_alone(self):
        meaning = self._generate_refused_with(WRONG_LINE)
        self.assertEqual(meaning.validated, Meaning.VALID)
        self.assertEqual(ValidationLog.query.filter_by(meaning_id=meaning.id).count(), 0)
