"""The validator's `cefr` for a meaning is stored as the meaning's word level,
both when the pair is valid and when the validator fixes it."""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.llm_services.translation_validator import ValidationResult
from zeeguu.core.llm_services.validation_service import UserWordValidationService
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class FakeValidator:
    def __init__(self, result):
        self.result = result

    def validate_translation(self, **kwargs):
        return self.result


class ValidatorStoresWordLevelTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.bookmark = BookmarkRule(UserRule().user).bookmark
        self.user_word = self.bookmark.user_word
        self.user_word.preferred_bookmark = self.bookmark
        session.add_all([self.bookmark, self.user_word])
        session.commit()

    def _validate(self, result):
        with patch(
            "zeeguu.core.llm_services.translation_validator.TranslationValidator",
            lambda: FakeValidator(result),
        ):
            return UserWordValidationService.validate_and_fix(session, self.user_word)

    def test_a_valid_pair_gets_the_validators_level(self):
        self._validate(ValidationResult(is_valid=True, cefr_level="A1"))
        self.assertEqual(self.user_word.meaning.word_cefr_level, "A1")

    def test_a_fixed_pair_gets_the_validators_level(self):
        new_word = self._validate(
            ValidationResult(is_valid=False, corrected_translation="something else entirely", cefr_level="A2", reason="wrong")
        )
        self.assertEqual(new_word.meaning.word_cefr_level, "A2")

    def test_no_level_leaves_it_alone(self):
        self.user_word.meaning.word_cefr_level = "B2"
        session.commit()
        self._validate(ValidationResult(is_valid=True))
        self.assertEqual(self.user_word.meaning.word_cefr_level, "B2")
