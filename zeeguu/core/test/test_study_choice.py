"""Whether a word is studied: the learner's study_choice, then the system's
unfit_reason. A STUDY choice lifts only the quality heuristics."""
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.bookmark_quality.fit_for_study import fit_given
from zeeguu.core.model.study_choice import StudyChoice, UnfitReason
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class FitGivenTest(TestCase):
    def test_skip_and_known_keep_any_word_out(self):
        for choice in (StudyChoice.SKIP, StudyChoice.KNOWN):
            self.assertFalse(fit_given(choice, None))

    def test_no_reason_no_choice_is_fit(self):
        self.assertTrue(fit_given(None, None))

    def test_study_lifts_a_quality_heuristic(self):
        self.assertFalse(fit_given(None, UnfitReason.SAME_AS_TRANSLATION))
        self.assertTrue(fit_given(StudyChoice.STUDY, UnfitReason.SAME_AS_TRANSLATION))

    def test_study_does_not_lift_a_verdict_or_a_separated_mwe(self):
        for reason in (
            UnfitReason.VALIDATOR_INVALID,
            UnfitReason.VALIDATOR_GAVE_UP,
            UnfitReason.REPLACED_BY_FIX,
            UnfitReason.DUPLICATE_MEANING,
            UnfitReason.NO_USABLE_CONTEXT,
            UnfitReason.SEPARATED_MWE,
        ):
            self.assertFalse(fit_given(StudyChoice.STUDY, reason), reason)

    def test_every_reason_is_liftable_sticky_or_judged_again(self):
        judged_again = {
            UnfitReason.SEPARATED_MWE,
            UnfitReason.VALIDATOR_GAVE_UP,
            UnfitReason.NO_USABLE_CONTEXT,
        }
        self.assertEqual(
            set(UnfitReason.ALL), UnfitReason.LIFTABLE | UnfitReason.STICKY | judged_again
        )


class UnfitReasonOnUserWordTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        bookmark = BookmarkRule(UserRule().user).bookmark
        self.user_word = bookmark.user_word
        self.user_word.preferred_bookmark = bookmark
        session.add(self.user_word)
        session.commit()

    def _recompute(self):
        with patch("zeeguu.core.bookmark_quality.fit_for_study.bad_quality_reason", lambda uw: None):
            self.user_word.update_fit_for_study(session)

    def test_a_sticky_verdict_survives_a_recompute(self):
        self.user_word.set_unfit_for_study(session, UnfitReason.REPLACED_BY_FIX)
        self._recompute()
        self.assertEqual(self.user_word.unfit_reason, UnfitReason.REPLACED_BY_FIX)
        self.assertFalse(self.user_word.fit_for_study)

    def test_a_give_up_is_judged_again_at_the_next_recompute(self):
        self.user_word.set_unfit_for_study(session, UnfitReason.VALIDATOR_GAVE_UP)
        self._recompute()
        self.assertIsNone(self.user_word.unfit_reason)
        self.assertTrue(self.user_word.fit_for_study)

    def test_the_failing_quality_check_is_the_reason(self):
        with patch(
            "zeeguu.core.bookmark_quality.fit_for_study.bad_quality_reason",
            lambda uw: UnfitReason.TOO_SHORT,
        ):
            self.user_word.update_fit_for_study(session)
            self.assertEqual(self.user_word.unfit_reason, UnfitReason.TOO_SHORT)
            self.assertFalse(self.user_word.fit_for_study)

            self.user_word.choose(session, StudyChoice.STUDY)
            self.assertTrue(self.user_word.fit_for_study)
            self.assertEqual(self.user_word.unfit_reason, UnfitReason.TOO_SHORT)  # lifted, still known

    def test_known_takes_a_fit_word_out(self):
        self._recompute()
        self.user_word.choose(session, StudyChoice.KNOWN)
        self.assertFalse(self.user_word.fit_for_study)
