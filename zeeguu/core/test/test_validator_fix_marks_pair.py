"""What a validator FIX does to the old pair: it becomes INVALID. Other
learners' words on it are never touched here; the nightly
validate_scheduled_meanings judges each in its own sentence."""
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.llm_services.translation_validator import ValidationResult
from zeeguu.core.llm_services.validation_service import UserWordValidationService
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.validation_log import ValidationLog
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord

session = zeeguu.core.model.db.session


class FakeValidator:
    def __init__(self, result):
        self.result = result

    def validate_translation(self, **kwargs):
        return self.result


class ValidatorTakesOutOtherLearnersTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        bookmark = BookmarkRule(UserRule().user).bookmark
        self.user_word = bookmark.user_word
        self.user_word.preferred_bookmark = bookmark
        self.meaning = self.user_word.meaning

        # Another learner already studying the same pair, and one who learned it
        self.other = BookmarkRule(UserRule().user).bookmark.user_word
        self.done = BookmarkRule(UserRule().user).bookmark.user_word
        for w in (self.other, self.done):
            w.meaning = self.meaning
            w.fit_for_study = True
        self.done.learned_time = datetime.now()
        self.meaning.validated = Meaning.VALID  # so scheduling the other skips the validator
        session.add_all([self.user_word, self.other, self.done, self.meaning])
        session.commit()
        FourLevelsPerWord.find_or_create(session, self.other)
        self.meaning.validated = Meaning.NOT_VALIDATED
        session.add(self.meaning)
        session.commit()

    def _validate(self, result):
        with patch(
            "zeeguu.core.llm_services.translation_validator.TranslationValidator",
            lambda: FakeValidator(result),
        ):
            UserWordValidationService.validate_and_fix(session, self.user_word)
        session.expire_all()

    def _assert_other_untouched(self):
        self.assertTrue(session.get(UserWord, self.other.id).fit_for_study)
        self.assertIsNotNone(BasicSRSchedule.query.filter_by(user_word_id=self.other.id).first())
        self.assertEqual(ValidationLog.query.filter_by(user_word_id=self.other.id).count(), 0)

    def test_a_translation_fix_marks_the_pair_invalid_and_leaves_others_alone(self):
        # A learner who met it in another sentence may have it right ('Bank'
        # = 'bench' on a park bench); they are judged in their own sentence
        self._validate(ValidationResult(is_valid=False, corrected_translation="entirely different", reason="wrong"))
        self.assertEqual(session.get(Meaning, self.meaning.id).validated, Meaning.INVALID)
        self._assert_other_untouched()

    def test_an_unfixable_pair_takes_out_this_learner_only(self):
        self._validate(ValidationResult(is_valid=False, reason="arbitrary fragment"))
        self.assertFalse(session.get(UserWord, self.user_word.id).fit_for_study)
        self.assertEqual(session.get(Meaning, self.meaning.id).validated, Meaning.INVALID)
        self._assert_other_untouched()

    def test_a_fix_that_changes_the_word_marks_the_pair_too(self):
        # Most such pairs are broken themselves ('bruger den' → 'are using it')
        word = self.meaning.origin.content
        self._validate(ValidationResult(
            is_valid=False, corrected_word=word + " af", corrected_translation="out of", reason="part of an expression"
        ))
        self.assertEqual(session.get(Meaning, self.meaning.id).validated, Meaning.INVALID)
        self._assert_other_untouched()

    def test_a_valid_pair_leaves_other_learners_alone(self):
        self._validate(ValidationResult(is_valid=True))
        self._assert_other_untouched()
