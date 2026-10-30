"""ADR 022: ``_vote_translation`` attaches an ``alternatives``
list to its return dict so the frontend can render the alternatives menu
directly, without a second round of provider calls.

These tests pin the shape (deduped, vote-ordered, winner first) across the
four return paths: no provider succeeded, single provider succeeded, all
providers agreed, providers disagreed.
"""

from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.translation_services import translator


def _provider_result(translation, source):
    """Render the minimal result dict the voter accepts from a provider."""
    return {"translation": translation, "source": source, "likelihood": 90}


class VoterAlternativesTest(TestCase):

    def setUp(self):
        self.data = {
            "source_language": "da",
            "target_language": "en",
            "word": "tæt",
            "query": None,
            "context": "Han stod tæt på vinduet.",
        }

    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_all_three_agree(self, ms, azure, google, deepl):
        azure.return_value = _provider_result("close", "Azure - alignment")
        google.return_value = _provider_result("close", "Google - with context")
        deepl.return_value = _provider_result("close", "DeepL - with context")
        ms.return_value = None  # fallback, must not be consulted

        result = translator._vote_translation(self.data)

        self.assertEqual(result["translation"], "close")
        # DeepL represents a bucket it shares (provider preference DeepL > Google).
        self.assertEqual(result["alternatives"], [
            {"translation": "close", "source": "DeepL - with context", "votes": 3},
        ])
        # Legacy fields: no disagreement, no competing.
        self.assertNotIn("competing_translations", result)
        self.assertNotIn("disagreement", result)

    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_deepl_dissent_from_majority_flags_disagreement(self, ms, azure, google, deepl):
        azure.return_value = _provider_result("close", "Azure - alignment")
        google.return_value = _provider_result("close", "Google - with context")
        deepl.return_value = _provider_result("tight", "DeepL - with context")
        ms.return_value = None

        result = translator._vote_translation(self.data)

        # Google+Azure outvote DeepL 2-to-1, so "close" still wins...
        self.assertEqual(result["translation"], "close")
        self.assertEqual(result["alternatives"], [
            {"translation": "close", "source": "Google - with context", "votes": 2},
            {"translation": "tight", "source": "DeepL - with context", "votes": 1},
        ])
        # ...but because DeepL dissents, we flag disagreement so the client
        # auto-opens the menu instead of silently burying DeepL's answer.
        self.assertTrue(result["disagreement"])
        # Legacy field still present during deprecation window.
        self.assertEqual(result["competing_translations"], [
            {"translation": "tight", "source": "DeepL - with context"},
        ])

    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_three_way_split_flags_disagreement(self, ms, azure, google, deepl):
        azure.return_value = _provider_result("close", "Azure - alignment")
        google.return_value = _provider_result("tight", "Google - with context")
        deepl.return_value = _provider_result("near", "DeepL - with context")
        ms.return_value = None

        result = translator._vote_translation(self.data)

        # All three buckets are size 1; provider preference (DeepL > Google >
        # Azure) breaks the tie, so DeepL's "near" wins.
        self.assertEqual(result["translation"], "near")
        self.assertEqual([alt["votes"] for alt in result["alternatives"]], [1, 1, 1])
        self.assertEqual(
            {alt["translation"] for alt in result["alternatives"]},
            {"tight", "near", "close"},
        )
        self.assertTrue(result["disagreement"])

    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_only_one_provider_succeeded(self, ms, azure, google, deepl):
        azure.return_value = None
        google.return_value = _provider_result("close", "Google - with context")
        deepl.return_value = None
        ms.return_value = None

        result = translator._vote_translation(self.data)

        self.assertEqual(result["translation"], "close")
        self.assertEqual(result["alternatives"], [
            {"translation": "close", "source": "Google - with context", "votes": 1},
        ])

    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_all_three_fail_falls_back_to_microsoft_with_alternatives(self, ms, azure, google, deepl):
        azure.return_value = None
        google.return_value = None
        deepl.return_value = None
        ms.return_value = _provider_result("close", "Microsoft - with context")

        result = translator._vote_translation(self.data)

        self.assertEqual(result["translation"], "close")
        self.assertEqual(result["alternatives"], [
            {"translation": "close", "source": "Microsoft - with context", "votes": 1},
        ])

    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_all_fail_including_fallback_returns_none(self, ms, azure, google, deepl):
        azure.return_value = None
        google.return_value = None
        deepl.return_value = None
        ms.return_value = None

        result = translator._vote_translation(self.data)

        self.assertIsNone(result)


class PhraseVoterTest(TestCase):
    """Multi-word selections add the contextless Google phrase translation as
    a fourth voter instead of returning it unchecked."""

    def setUp(self):
        self.data = {
            "source_language": "da",
            "target_language": "en",
            "word": "en bonde",
            "query": None,
            "context": "For jeg' en bonde i et kongespil",
        }

    @patch.object(translator, "translate_mwe_phrase")
    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_phrase_voter_not_consulted_for_single_words(self, ms, azure, google, deepl, phrase):
        azure.return_value = _provider_result("close", "Azure - alignment")
        google.return_value = _provider_result("close", "Google - with context")
        deepl.return_value = _provider_result("close", "DeepL - with context")

        translator._vote_translation(self.data)

        phrase.assert_not_called()

    @patch.object(translator, "translate_mwe_phrase")
    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_two_two_split_flags_disagreement(self, ms, azure, google, deepl, phrase):
        # The chess case: both Google calls miss the context, DeepL and
        # Azure get it. A 2-2 split is not a consensus.
        phrase.return_value = _provider_result("a farmer", "Google - MWE phrase")
        google.return_value = _provider_result("a farmer", "Google - with context")
        deepl.return_value = _provider_result("a pawn", "DeepL - with context")
        azure.return_value = _provider_result("a pawn", "Azure - alignment")

        result = translator._vote_translation(self.data, phrase=True)

        # DeepL's bucket wins the tie on provider preference.
        self.assertEqual(result["translation"], "a pawn")
        self.assertEqual([alt["votes"] for alt in result["alternatives"]], [2, 2])
        self.assertTrue(result["disagreement"])

    @patch.object(translator, "translate_mwe_phrase")
    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_phrase_voter_can_carry_a_grammatical_mwe(self, ms, azure, google, deepl, phrase):
        # The reason the phrase call exists: contextual Google misreads
        # "vil have fjernet" as "want to remove".
        phrase.return_value = _provider_result("will have removed", "Google - MWE phrase")
        google.return_value = _provider_result("want to remove", "Google - with context")
        deepl.return_value = _provider_result("will have removed", "DeepL - with context")
        azure.return_value = _provider_result("will have removed", "Azure - alignment")

        result = translator._vote_translation(dict(self.data, word="vil have fjernet"), phrase=True)

        self.assertEqual(result["translation"], "will have removed")
        self.assertEqual(result["alternatives"][0]["votes"], 3)
        self.assertNotIn("disagreement", result)

    @patch.object(translator, "translate_mwe_phrase")
    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_four_way_split_flags_disagreement(self, ms, azure, google, deepl, phrase):
        phrase.return_value = _provider_result("is frozen to", "Google - MWE phrase")
        google.return_value = _provider_result("are frozen", "Google - with context")
        deepl.return_value = _provider_result("am frozen solid", "DeepL - with context")
        azure.return_value = _provider_result("are frozen to", "Azure - alignment")

        result = translator._vote_translation(dict(self.data, word="er frosset til"), phrase=True)

        self.assertEqual(result["translation"], "am frozen solid")
        # Tie order: DeepL > Google > Google phrase > Azure.
        self.assertEqual(
            [alt["translation"] for alt in result["alternatives"]],
            ["am frozen solid", "are frozen", "is frozen to", "are frozen to"],
        )
        self.assertTrue(result["disagreement"])
