"""A validator verdict keeps which engine produced the translation it judged,
even when a fix moves the bookmark to the validator's own pair."""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.llm_services.translation_validator import ValidationResult
from zeeguu.core.llm_services.validation_service import UserWordValidationService
from zeeguu.core.model import TranslationService
from zeeguu.core.model.validation_log import ValidationAction, ValidationLog
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class FakeValidator:
    def __init__(self, result):
        self.result = result

    def validate_translation(self, **kwargs):
        return self.result


class ValidationLogTranslationServiceTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.bookmark = BookmarkRule(UserRule().user).bookmark
        self.bookmark.set_translation_service(session, "Google - without context")
        self.user_word = self.bookmark.user_word
        self.user_word.preferred_bookmark = self.bookmark
        session.add_all([self.bookmark, self.user_word])
        session.commit()
        self.deepl_id = self.bookmark.translation_service_id
        self.assertIsNotNone(self.deepl_id)

    def _validate(self, result):
        with patch(
            "zeeguu.core.llm_services.translation_validator.TranslationValidator",
            lambda: FakeValidator(result),
        ):
            return UserWordValidationService.validate_and_fix(session, self.user_word)

    def test_a_fix_logs_the_engine_it_corrected_and_marks_the_bookmark_as_fixed(self):
        new_word = self._validate(
            ValidationResult(is_valid=False, corrected_translation="something else entirely", reason="wrong")
        )
        logged = ValidationLog.query.one()
        self.assertEqual(logged.action, ValidationAction.FIXED)
        self.assertEqual(logged.translation_service_id, self.deepl_id)
        self.assertEqual(self.bookmark.translation_service.name, TranslationService.VALIDATOR)
        self.assertNotEqual(new_word.id, self.user_word.id)

    def test_a_valid_verdict_logs_the_engine(self):
        self._validate(ValidationResult(is_valid=True))
        self.assertEqual(ValidationLog.query.one().translation_service_id, self.deepl_id)

    def test_one_row_per_service(self):
        first = TranslationService.find_or_create(session, "DeepL")
        again = TranslationService.find_or_create(session, "DeepL")
        self.assertEqual(first.id, again.id)
        self.assertIsNotNone(first.id)
