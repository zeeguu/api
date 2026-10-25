"""A wrong_translation report runs the validator on the word in the reported
sentence, even when the meaning was already judged VALID, and keeps its
verdict."""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.llm_services.translation_validator import ValidationResult, WORD_NOT_FIT
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.validation_log import ValidationLog
from zeeguu.core.model.word_report import WordReport
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.word_reports import judge

session = zeeguu.core.model.db.session


class FakeValidator:
    def __init__(self, result):
        self.result = result
        self.contexts = []

    def validate_translation(self, **kwargs):
        self.contexts.append(kwargs["context"])
        return self.result


class WordReportJudgedTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.bookmark = BookmarkRule(self.user).bookmark
        self.user_word = self.bookmark.user_word
        self.user_word.preferred_bookmark = self.bookmark
        self.user_word.meaning.validated = Meaning.VALID
        session.add_all([self.user_word, self.user_word.meaning])
        session.commit()
        self.report = WordReport.for_bookmark(
            session, self.user, self.bookmark, WordReport.WRONG_TRANSLATION, WordReport.EXERCISE
        )

    def _judge(self, result):
        validator = FakeValidator(result)
        with patch(
            "zeeguu.core.llm_services.translation_validator.TranslationValidator",
            lambda: validator,
        ):
            judge(session, self.report)
        return validator

    def test_a_valid_meaning_is_judged_again_in_the_reported_sentence(self):
        validator = self._judge(ValidationResult(is_valid=True))

        self.assertEqual(validator.contexts, [self.bookmark.get_context()])
        self.assertEqual(self.report.outcome, "valid")
        self.assertEqual(ValidationLog.query.get(self.report.validation_log_id).meaning_id,
                         self.report.meaning_id)
        self.assertIsNotNone(self.report.judged_at)

    def test_a_fix_moves_the_learner_and_is_kept_on_the_report(self):
        old_meaning = self.user_word.meaning

        self._judge(ValidationResult(
            is_valid=False, corrected_translation="entirely different", reason="wrong"
        ))

        self.assertEqual(self.report.outcome, "fixed")
        self.assertEqual(old_meaning.validated, Meaning.INVALID)
        self.assertEqual(self.report.meaning, old_meaning)  # what was reported
        session.refresh(self.bookmark)
        self.assertEqual(self.bookmark.user_word.meaning.translation.content, "entirely different")

    def test_a_give_up_is_kept(self):
        self._judge(ValidationResult(is_valid=False, gave_up=WORD_NOT_FIT, reason="no meaning fits"))

        self.assertEqual(self.report.outcome, "gave_up")
        self.assertIsNone(self.report.validation_log_id)

    def test_no_verdict_leaves_the_report_to_be_judged_again(self):
        self._judge(None)

        self.assertIsNone(self.report.outcome)
        self.assertIsNone(self.report.judged_at)

    def test_a_word_that_moved_on_since_is_not_judged(self):
        self.bookmark.user_word = UserWord.find_or_create(
            session, self.user, BookmarkRule(self.user).bookmark.user_word.meaning
        )
        session.add(self.bookmark)
        session.commit()

        validator = self._judge(ValidationResult(is_valid=True))

        self.assertEqual(validator.contexts, [])
        self.assertEqual(self.report.outcome, "not_judged")
