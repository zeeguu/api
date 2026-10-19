"""When the translation validator finds a pair broken for one learner, the
other learners' unlearned words on it leave study too."""
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

    def _assert_other_taken_out(self):
        self.assertFalse(session.get(UserWord, self.other.id).fit_for_study)
        self.assertIsNone(BasicSRSchedule.query.filter_by(user_word_id=self.other.id).first())
        self.assertTrue(session.get(UserWord, self.done.id).fit_for_study)
        logged = ValidationLog.query.filter_by(user_word_id=self.other.id).one()
        self.assertTrue(logged.reason.startswith("[another learner's validation]"))

    def test_a_fix_takes_the_broken_pair_out_for_other_learners(self):
        self._validate(ValidationResult(is_valid=False, corrected_translation="entirely different", reason="wrong"))
        self._assert_other_taken_out()
        self.assertEqual(session.get(Meaning, self.meaning.id).validated, Meaning.INVALID)

    def test_an_unfixable_pair_is_taken_out_for_other_learners_and_this_one(self):
        self.meaning.validated = Meaning.VALID  # so scheduling skips the validator
        session.add(self.meaning)
        session.commit()
        FourLevelsPerWord.find_or_create(session, self.user_word)
        self.meaning.validated = Meaning.NOT_VALIDATED
        session.add(self.meaning)
        session.commit()
        self._validate(ValidationResult(is_valid=False, reason="arbitrary fragment"))
        self._assert_other_taken_out()
        # It used to become unfit but stay scheduled
        self.assertIsNone(BasicSRSchedule.query.filter_by(user_word_id=self.user_word.id).first())
        self.assertEqual(ValidationLog.query.filter_by(user_word_id=self.user_word.id).count(), 1)

    def test_a_valid_pair_leaves_other_learners_alone(self):
        self._validate(ValidationResult(is_valid=True))
        self.assertTrue(session.get(UserWord, self.other.id).fit_for_study)
        self.assertIsNotNone(BasicSRSchedule.query.filter_by(user_word_id=self.other.id).first())

    def test_a_fix_that_changes_the_word_leaves_other_learners_alone(self):
        # 'ud' in 'ud af' → 'ud af' = 'out of': this learner selected too
        # little; 'ud' = 'out' still holds for the others
        word = self.meaning.origin.content
        self._validate(ValidationResult(
            is_valid=False, corrected_word=word + " af", corrected_translation="out of", reason="part of an expression"
        ))
        self.assertTrue(session.get(UserWord, self.other.id).fit_for_study)
        self.assertIsNotNone(BasicSRSchedule.query.filter_by(user_word_id=self.other.id).first())
        # and the old pair is not stamped broken, so it keeps its audio lessons
        self.assertNotEqual(session.get(Meaning, self.meaning.id).validated, Meaning.INVALID)
