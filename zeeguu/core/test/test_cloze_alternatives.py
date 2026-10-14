"""Judging another word typed into a cloze, and sharing the verdict.

The LLM is replaced by a fake that counts its calls: the point of
meaning_alternative is that each (meaning, typed word) is judged once.
"""
from unittest import TestCase

import zeeguu.core
from zeeguu.core.exercises.cloze_alternatives import (
    UNKNOWN,
    blank_out,
    judge_alternative,
    normalize,
)
from zeeguu.core.llm_services.cloze_alternative_judge import ClozeAlternativeVerdict
from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.meaning_alternative import MeaningAlternative
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.word_scheduling.basicSR.basicSR import _counts_as_progress

session = zeeguu.core.model.db.session


class FakeJudge:
    MODEL_NAME = "fake-judge"

    def __init__(self, relation=MeaningAlternative.SYNONYM, context_specific=False, explanation=""):
        self.verdict = ClozeAlternativeVerdict(relation, context_specific, explanation)
        self.calls = []

    def judge(self, **kwargs):
        self.calls.append(kwargs)
        return self.verdict


class DownJudge(FakeJudge):
    def judge(self, **kwargs):
        self.calls.append(kwargs)
        return None


class ClozeAlternativesTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.bookmark = BookmarkRule(self.user).bookmark

    def _bookmark_of_another_learner_in(self, sentence_like):
        """Same meaning, another learner, possibly another sentence."""
        other = BookmarkRule(UserRule().user).bookmark
        other.user_word.meaning = self.bookmark.user_word.meaning
        if sentence_like is not None:
            other.context = sentence_like.context
            other.text = sentence_like.text
        session.add_all([other, other.user_word])
        session.commit()
        return other

    def test_a_verdict_is_judged_once_and_shared(self):
        judge = FakeJudge(MeaningAlternative.SYNONYM)

        first = judge_alternative(session, self.bookmark, "  Tænker ", judge=judge)
        again = judge_alternative(session, self.bookmark, "tænker", judge=judge)
        other_learner = self._bookmark_of_another_learner_in(sentence_like=None)
        theirs = judge_alternative(session, other_learner, "tænker", judge=judge)

        self.assertEqual(len(judge.calls), 1)
        self.assertEqual((first["relation"], first["cached"]), ("SYNONYM", False))
        self.assertEqual((again["relation"], again["cached"]), ("SYNONYM", True))
        self.assertEqual((theirs["relation"], theirs["cached"]), ("SYNONYM", True))

    def test_a_context_specific_verdict_is_only_reused_in_its_sentence(self):
        judge = FakeJudge(MeaningAlternative.NEAR_SYNONYM_NOT_IDIOMATIC, context_specific=True,
                          explanation="For opinions Danish uses 'synes'.")

        judge_alternative(session, self.bookmark, "tænker", judge=judge)
        same_sentence = self._bookmark_of_another_learner_in(sentence_like=self.bookmark)
        reused = judge_alternative(session, same_sentence, "tænker", judge=judge)
        other_sentence = self._bookmark_of_another_learner_in(sentence_like=None)
        judge_alternative(session, other_sentence, "tænker", judge=judge)

        self.assertTrue(reused["cached"])
        self.assertEqual(reused["explanation"], "For opinions Danish uses 'synes'.")
        self.assertEqual(len(judge.calls), 2)

    def test_when_the_judge_is_down_nothing_is_stored(self):
        result = judge_alternative(session, self.bookmark, "tænker", judge=DownJudge())

        self.assertEqual(result["relation"], UNKNOWN)
        self.assertEqual(MeaningAlternative.query.count(), 0)

    def test_the_expected_word_and_overlong_answers_skip_the_judge(self):
        judge = FakeJudge()
        expected = self.bookmark.user_word.meaning.origin.content

        self.assertEqual(judge_alternative(session, self.bookmark, expected.upper(), judge=judge)["relation"], "SYNONYM")
        self.assertEqual(judge_alternative(session, self.bookmark, "x" * 61, judge=judge)["relation"], "NOT_SYNONYM")
        self.assertEqual(judge.calls, [])

    def test_the_judge_gets_the_word_its_translation_and_the_sentence(self):
        judge = FakeJudge()
        judge_alternative(session, self.bookmark, "Tænker", judge=judge)

        meaning = self.bookmark.user_word.meaning
        call = judge.calls[0]
        self.assertEqual(call["expected"], meaning.origin.content)
        self.assertEqual(call["translation"], meaning.translation.content)
        self.assertEqual(call["typed"], "tænker")
        self.assertEqual(call["blanked"], blank_out(self.bookmark.get_context(), meaning.origin.content))


class ClozeAlternativeHelpersTest(TestCase):
    def test_normalize(self):
        self.assertEqual(normalize("  Tænker  meget "), "tænker meget")

    def test_blank_out_matches_whole_words_case_insensitively(self):
        self.assertEqual(blank_out("Synes du, at synesthesia...", "synes"), "___ du, at synesthesia...")
        self.assertEqual(blank_out("Han har breve som skal sendes", "som skal"), "Han har breve ___ sendes")
        self.assertEqual(blank_out("no match here", "synes"), "no match here")

    def test_an_alternative_moves_the_word_forward_but_is_not_a_clean_answer(self):
        self.assertTrue(_counts_as_progress(ExerciseOutcome.ALTERNATIVE))
        self.assertFalse(ExerciseOutcome.is_correct(ExerciseOutcome.ALTERNATIVE))
        self.assertTrue(ExerciseOutcome.is_valid_attempt("WA"))
