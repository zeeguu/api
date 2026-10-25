"""A validator FIX moves the learner to the corrected pair, and the corrected
pair is judged by the quality checks like any other: being fit for study
before the fix is not the learner opting in. On 2026-10-22 'Waymo' -> 'op
Waymo' was fixed to 'Waymo' -> 'Waymo' and forced into study anyway."""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.llm_services.translation_validator import ValidationResult
from zeeguu.core.llm_services.validation_service import UserWordValidationService
from zeeguu.core.model.study_choice import StudyChoice
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class FakeValidator:
    def __init__(self, result):
        self.result = result

    def validate_translation(self, **kwargs):
        return self.result


class ValidatorFixKeepsQualityChecksTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        bookmark = BookmarkRule(UserRule().user).bookmark
        self.user_word = bookmark.user_word
        self.user_word.preferred_bookmark = bookmark
        self.user_word.fit_for_study = True
        self.user_word.meaning.validated = Meaning.NOT_VALIDATED
        session.add_all([self.user_word, self.user_word.meaning])
        session.commit()

    def _fix_to_the_word_itself(self):
        # A name the learner's language writes the same: fails origin_same_as_translation
        word = self.user_word.meaning.origin.content
        with patch(
            "zeeguu.core.llm_services.translation_validator.TranslationValidator",
            lambda: FakeValidator(ValidationResult(
                is_valid=False, corrected_translation=word, reason="proper noun, same in both languages"
            )),
        ):
            return UserWordValidationService.validate_and_fix(session, self.user_word)

    def test_a_fix_to_an_unfit_pair_leaves_it_unfit(self):
        new_user_word = self._fix_to_the_word_itself()
        self.assertNotEqual(new_user_word.id, self.user_word.id)
        self.assertFalse(new_user_word.fit_for_study)
        self.assertIsNone(new_user_word.study_choice)

    def test_the_learners_own_opt_in_carries_over(self):
        self.user_word.study_choice = StudyChoice.STUDY
        session.add(self.user_word)
        session.commit()
        new_user_word = self._fix_to_the_word_itself()
        self.assertTrue(new_user_word.fit_for_study)
        self.assertEqual(new_user_word.study_choice, StudyChoice.STUDY)
