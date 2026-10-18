"""When the lesson check finds the word/translation pair itself wrong, the
meaning is marked INVALID, and the mark outlives the caller's rollback."""
from datetime import datetime
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
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord

session = zeeguu.core.model.db.session

WRONG_PAIR = [{"line": 4, "text": "Teacher: experienced.", "kind": "translation", "issue": "connu is 'known'"}]
WRONG_LINE = [{"line": 9, "text": "Man: x", "kind": "sense", "issue": "wrong sense"}]


class LessonCheckMarksPairTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user_word = BookmarkRule(UserRule().user).bookmark.user_word
        self.meaning = self.user_word.meaning
        self.meaning.validated = Meaning.VALID
        self.user_word.fit_for_study = True
        session.add_all([self.meaning, self.user_word])
        session.commit()
        FourLevelsPerWord.find_or_create(session, self.user_word)

        # Two other learners with the same pair: one still learning it, one done.
        self.other = BookmarkRule(UserRule().user).bookmark.user_word
        self.done = BookmarkRule(UserRule().user).bookmark.user_word
        for other in (self.other, self.done):
            other.meaning = self.meaning
            other.fit_for_study = True
        self.done.learned_time = datetime.now()
        session.add_all([self.other, self.done])
        session.commit()
        FourLevelsPerWord.find_or_create(session, self.other)

    def _generate_refused_with(self, problems):
        def refuse(**kwargs):
            raise LessonNotCorrect("refused", problems, about_the_data=problems is WRONG_PAIR)

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
        logged = ValidationLog.query.filter_by(meaning_id=meaning.id).all()
        # One per word taken out of study, so each answers why; not the learned one.
        self.assertEqual({l.user_word_id for l in logged}, {self.user_word.id, self.other.id})
        for entry in logged:
            self.assertEqual(entry.action, ValidationAction.INVALID)
            self.assertEqual(entry.reason, "[audio lesson check] connu is 'known'")

    def test_a_wrong_pair_takes_unlearned_words_out_of_study_for_everyone(self):
        self.assertEqual(BasicSRSchedule.query.count(), 2)
        self._generate_refused_with(WRONG_PAIR)
        fit = {w.id: w.fit_for_study for w in UserWord.query.filter_by(meaning_id=self.meaning.id)}
        self.assertEqual(fit, {self.user_word.id: False, self.other.id: False, self.done.id: True})
        self.assertEqual(BasicSRSchedule.query.count(), 0)

    def test_a_wrong_script_leaves_the_meaning_alone(self):
        meaning = self._generate_refused_with(WRONG_LINE)
        self.assertEqual(meaning.validated, Meaning.VALID)
        self.assertEqual(ValidationLog.query.filter_by(meaning_id=meaning.id).count(), 0)
        self.assertEqual(BasicSRSchedule.query.count(), 2)

    def test_a_failed_mark_still_ends_in_the_refusal_not_another_error(self):
        # The daily lesson leaves a refused word out; any other error fails it
        with patch.object(
            daily_lesson_generator, "mark_pair_invalid", side_effect=RuntimeError("lock wait timeout")
        ):
            meaning = self._generate_refused_with(WRONG_PAIR)
        self.assertEqual(meaning.validated, Meaning.VALID)

    def test_a_deleted_context_is_not_sent_as_the_sentence(self):
        from zeeguu.core.audio_lessons.daily_lesson_generator import _lookup_sentence
        from zeeguu.core.model import Bookmark

        self.user_word.preferred_bookmark = Bookmark.query.filter_by(user_word_id=self.user_word.id).first()
        self.assertIsNotNone(_lookup_sentence(self.user_word))
        with patch.object(type(self.user_word.preferred_bookmark), "get_context", lambda b: "[Context deleted]"):
            self.assertIsNone(_lookup_sentence(self.user_word))
