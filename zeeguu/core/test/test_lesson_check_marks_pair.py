"""What happens to a word when the lesson check refuses its lesson: a pair
confirmed wrong is fixed the way the translation validator fixes one (after
the caller's transaction), anything else is remembered as a refusal."""
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.audio_lessons import daily_lesson_generator
from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator
from zeeguu.core.audio_lessons.script_generator import LessonNotCorrect, NotAScript, MEANING_LESSON_PROMPT_VERSION
from zeeguu.core.llm_services.translation_validator import ValidationResult
from zeeguu.core.model.audio_lesson_refusal import AudioLessonRefusal
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
FIXABLE = ValidationResult(is_valid=False, corrected_translation="known", reason="connu is 'known'")
UNFIXABLE = ValidationResult(is_valid=False, reason="not a learning unit")


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

    def _generate_refused_with(self, problems, raising=None, pair_verdict=None):
        refusal = raising or LessonNotCorrect("refused", problems, pair_verdict=pair_verdict)

        def refuse(**kwargs):
            raise refusal

        generator = DailyLessonGenerator.__new__(DailyLessonGenerator)
        with patch.object(daily_lesson_generator, "generate_lesson_script", refuse):
            with self.assertRaises((LessonNotCorrect, NotAScript)):
                generator.generate_audio_lesson_meaning(
                    self.user_word, "da", "en", "A1", voice_variety=None
                )
        session.rollback()  # what the callers do, before applying the fix
        if isinstance(refusal, LessonNotCorrect) and refusal.about_the_data:
            generator.fix_refused_pair(session.get(UserWord, self.user_word.id), refusal)
        session.expire_all()
        return session.get(Meaning, self.meaning.id)

    def _fit(self, user_word):
        return session.get(UserWord, user_word.id).fit_for_study

    def _scheduled(self, user_word_id):
        return BasicSRSchedule.query.filter_by(user_word_id=user_word_id).first() is not None

    def test_a_fixable_pair_moves_the_learner_to_the_correction(self):
        from zeeguu.core.model import Bookmark

        bookmark_id = Bookmark.query.filter_by(user_word_id=self.user_word.id).first().id
        meaning = self._generate_refused_with(WRONG_PAIR, pair_verdict=FIXABLE)
        self.assertEqual(meaning.validated, Meaning.INVALID)

        moved_to = session.get(Bookmark, bookmark_id).user_word
        self.assertEqual(moved_to.meaning.translation.content, "known")
        self.assertTrue(self._scheduled(moved_to.id))  # the progress came along
        self.assertEqual(moved_to.user_id, self.user_word.user_id)

    def test_a_fixable_pair_takes_it_out_for_other_learners(self):
        self._generate_refused_with(WRONG_PAIR, pair_verdict=FIXABLE)
        self.assertFalse(self._fit(self.other))
        self.assertFalse(self._scheduled(self.other.id))
        self.assertTrue(self._fit(self.done))

    def test_an_unfixable_pair_takes_it_out_for_everyone(self):
        meaning = self._generate_refused_with(WRONG_PAIR, pair_verdict=UNFIXABLE)
        self.assertEqual(meaning.validated, Meaning.INVALID)
        for user_word in (self.user_word, self.other):
            self.assertFalse(self._fit(user_word))
            self.assertFalse(self._scheduled(user_word.id))
        self.assertTrue(self._fit(self.done))
        self.assertEqual(
            {l.user_word_id for l in ValidationLog.query.filter_by(meaning_id=meaning.id)},
            {self.user_word.id, self.other.id},
        )

    def test_a_wrong_script_leaves_the_meaning_alone(self):
        meaning = self._generate_refused_with(WRONG_LINE)
        self.assertEqual(meaning.validated, Meaning.VALID)
        self.assertEqual(ValidationLog.query.filter_by(meaning_id=meaning.id).count(), 0)
        self.assertEqual(BasicSRSchedule.query.count(), 2)

    def test_a_failed_record_still_ends_in_the_refusal_not_another_error(self):
        # The daily lesson leaves a refused word out; any other error fails it
        with patch.object(AudioLessonRefusal, "record", side_effect=RuntimeError("lock wait timeout")):
            meaning = self._generate_refused_with(WRONG_LINE)
        self.assertEqual(meaning.validated, Meaning.VALID)

    def test_a_failed_fix_is_reported_not_raised(self):
        generator = DailyLessonGenerator.__new__(DailyLessonGenerator)
        with patch(
            "zeeguu.core.llm_services.validation_service.UserWordValidationService.fix_with_verdict",
            side_effect=RuntimeError("lock wait timeout"),
        ):
            generator.fix_refused_pair(self.user_word, LessonNotCorrect("x", WRONG_PAIR, FIXABLE))
        self.assertEqual(session.get(Meaning, self.meaning.id).validated, Meaning.VALID)

    def test_a_deleted_context_is_not_sent_as_the_sentence(self):
        from zeeguu.core.audio_lessons.daily_lesson_generator import _lookup_sentence
        from zeeguu.core.model import Bookmark

        self.user_word.preferred_bookmark = Bookmark.query.filter_by(user_word_id=self.user_word.id).first()
        self.assertIsNotNone(_lookup_sentence(self.user_word))
        with patch.object(type(self.user_word.preferred_bookmark), "get_context", lambda b: "[Context deleted]"):
            self.assertIsNone(_lookup_sentence(self.user_word))

    def _refusal(self):
        return AudioLessonRefusal.query.filter_by(meaning_id=self.meaning.id).one_or_none()

    def test_a_script_still_wrong_is_remembered_and_the_pair_left_alone(self):
        meaning = self._generate_refused_with(WRONG_LINE)
        self.assertEqual(meaning.validated, Meaning.VALID)
        refusal = self._refusal()
        self.assertEqual(refusal.reason, AudioLessonRefusal.NOT_CORRECT)
        self.assertEqual(refusal.prompt_version, MEANING_LESSON_PROMPT_VERSION)

    def test_a_word_the_model_will_not_write_is_remembered(self):
        self._generate_refused_with([], raising=NotAScript("it said: 'amenaza means threat, not hot'"))
        refusal = self._refusal()
        self.assertEqual(refusal.reason, AudioLessonRefusal.NOT_A_SCRIPT)
        self.assertIn("amenaza", refusal.detail)

    def test_a_wrong_pair_is_not_a_refusal(self):
        self._generate_refused_with(WRONG_PAIR, pair_verdict=FIXABLE)
        self.assertIsNone(self._refusal())
