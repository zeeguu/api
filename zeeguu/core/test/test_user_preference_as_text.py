"""user_word.user_preference is TEXT in prod (the model says Integer), so it
comes back as "-6" or "0". Code that does arithmetic or compares it as an int
must go through UserWordExPreference.of()."""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.bookmark_quality.fit_for_study import fit_for_study
from zeeguu.core.llm_services.translation_validator import ValidationResult
from zeeguu.core.llm_services.validation_service import UserWordValidationService
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class UserPreferenceAsTextTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.bookmark = BookmarkRule(self.user).bookmark
        self.user_word = self.bookmark.user_word
        self.meaning = self.user_word.meaning

    def test_looking_up_a_word_declared_known_again_erodes_the_text_value(self):
        self.user_word.user_preference = "-6"  # as prod returns it

        Bookmark.find_or_create(
            session, self.user,
            self.meaning.origin.content, self.meaning.origin.language.code,
            self.meaning.translation.content, self.meaning.translation.language.code,
            f"Det er {self.meaning.origin.content} her.", None, None,
            sentence_i=0, token_i=2, total_tokens=1, c_sentence_i=0, c_token_i=0,
            context_identifier=ContextIdentifier(context_type=ContextType.USER_EDITED_TEXT),
            translation_source="reading",
        )

        self.assertEqual(self.user_word.user_preference, UserWordExPreference.DECLARED_KNOWN + 2)

    def test_an_audio_lesson_adds_a_word_whose_preference_is_a_text_zero(self):
        from zeeguu.core.bookmark_operations.add_word_to_study import add_word_to_study

        self.user_word.user_preference = "0"  # no preference, as prod returns it
        session.add(self.user_word)

        added, _, _ = add_word_to_study(
            session, self.user, self.meaning.origin.content, self.meaning.translation.content,
            self.meaning.origin.language.code, self.meaning.translation.language.code,
            f"Det er {self.meaning.origin.content} her.", from_audio_lesson=True,
        )

        self.assertIsNotNone(added)  # added, not left alone


class ValidatorFixRecomputesFitTest(ModelTestMixIn, TestCase):
    def test_the_corrected_word_is_judged_again(self):
        bookmark = BookmarkRule(UserRule().user).bookmark
        user_word = bookmark.user_word
        user_word.preferred_bookmark = bookmark
        user_word.fit_for_study = True
        user_word.meaning.validated = Meaning.NOT_VALIDATED
        origin = user_word.meaning.origin
        corrected = Meaning.find_or_create(
            session, origin.content, origin.language.code, "corrected", user_word.meaning.translation.language.code
        )
        # the learner already has the corrected word, marked fit long ago
        existing = UserWord.find_or_create(session, user_word.user, corrected)
        existing.fit_for_study = True
        session.add_all([user_word, user_word.meaning, existing])
        session.commit()

        result = ValidationResult(is_valid=False, corrected_translation="corrected", reason="wrong sense")
        with patch(
            "zeeguu.core.llm_services.translation_validator.TranslationValidator",
            lambda: type("V", (), {"validate_translation": lambda self, **kw: result})(),
        ):
            new_user_word = UserWordValidationService.validate_and_fix(session, user_word)

        self.assertEqual(new_user_word.id, existing.id)
        self.assertFalse(fit_for_study(new_user_word))  # a rare word for a beginner
        self.assertFalse(new_user_word.fit_for_study)
