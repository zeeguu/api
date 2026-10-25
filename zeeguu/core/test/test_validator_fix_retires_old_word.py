"""After a validator FIX the old user word goes out of study, even when other
bookmarks keep it alive. On 2026-10-22 'Waymo' -> 'op Waymo' kept generated
example bookmarks, stayed fit, and was served and "fixed" again five times
in a minute."""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.llm_services.translation_validator import ValidationResult
from zeeguu.core.llm_services.validation_service import UserWordValidationService
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class FakeValidator:
    def __init__(self, result):
        self.result = result

    def validate_translation(self, **kwargs):
        return self.result


class ValidatorFixRetiresOldWordTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        user = UserRule().user
        bookmark = BookmarkRule(user).bookmark
        self.user_word = bookmark.user_word
        self.user_word.preferred_bookmark = bookmark
        self.user_word.fit_for_study = True
        self.user_word.meaning.validated = Meaning.NOT_VALIDATED
        session.add_all([self.user_word, self.user_word.meaning])
        session.commit()

    def _fix(self):
        with patch(
            "zeeguu.core.llm_services.translation_validator.TranslationValidator",
            lambda: FakeValidator(ValidationResult(
                is_valid=False, corrected_translation="entirely different", reason="wrong"
            )),
        ):
            return UserWordValidationService.validate_and_fix(session, self.user_word)

    def test_an_old_word_held_by_another_bookmark_leaves_study(self):
        # A second bookmark on the old pair, like a generated example placed for it
        other = BookmarkRule(self.user_word.user).bookmark
        other.user_word_id = self.user_word.id
        session.add(other)
        session.commit()
        old_id = self.user_word.id

        new_user_word = self._fix()
        session.expire_all()

        self.assertNotEqual(new_user_word.id, old_id)
        old = session.get(UserWord, old_id)
        self.assertIsNotNone(old)
        self.assertFalse(old.fit_for_study)

        # and it stays out when something recomputes the flag, even if the
        # quality checks pass
        with patch("zeeguu.core.bookmark_quality.fit_for_study.quality_meaning", lambda uw: True):
            old.update_fit_for_study(session)
        self.assertFalse(old.fit_for_study)

    def test_an_orphaned_old_word_is_still_deleted(self):
        old_id = self.user_word.id
        self._fix()
        session.expire_all()
        self.assertIsNone(session.get(UserWord, old_id))
