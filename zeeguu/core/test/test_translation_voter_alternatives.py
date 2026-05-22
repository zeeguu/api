"""ADR 022: ``_vote_single_word_translation`` attaches an ``alternatives``
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

        result = translator._vote_single_word_translation(self.data)

        self.assertEqual(result["translation"], "close")
        self.assertEqual(result["alternatives"], [
            {"translation": "close", "source": "Google - with context", "votes": 3},
        ])
        # Legacy fields: no disagreement, no competing.
        self.assertNotIn("competing_translations", result)
        self.assertNotIn("disagreement", result)

    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_two_vs_one_splits_into_two_alternatives(self, ms, azure, google, deepl):
        azure.return_value = _provider_result("close", "Azure - alignment")
        google.return_value = _provider_result("close", "Google - with context")
        deepl.return_value = _provider_result("tight", "DeepL - with context")
        ms.return_value = None

        result = translator._vote_single_word_translation(self.data)

        # Winner is the 2-vote bucket; loser bucket follows.
        self.assertEqual(result["translation"], "close")
        self.assertEqual(result["alternatives"], [
            {"translation": "close", "source": "Google - with context", "votes": 2},
            {"translation": "tight", "source": "DeepL - with context", "votes": 1},
        ])
        # Legacy fields still present during deprecation window.
        self.assertEqual(result["competing_translations"], [
            {"translation": "tight", "source": "DeepL - with context"},
        ])
        self.assertNotIn("disagreement", result)

    @patch.object(translator, "deepl_contextual_translate_cached")
    @patch.object(translator, "google_contextual_translate")
    @patch.object(translator, "azure_alignment_contextual_translate")
    @patch.object(translator, "microsoft_contextual_translate")
    def test_three_way_split_flags_disagreement(self, ms, azure, google, deepl):
        azure.return_value = _provider_result("close", "Azure - alignment")
        google.return_value = _provider_result("tight", "Google - with context")
        deepl.return_value = _provider_result("near", "DeepL - with context")
        ms.return_value = None

        result = translator._vote_single_word_translation(self.data)

        # All three buckets are size 1; provider preference (Google > DeepL >
        # Azure) breaks the tie, so Google's "tight" wins.
        self.assertEqual(result["translation"], "tight")
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

        result = translator._vote_single_word_translation(self.data)

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

        result = translator._vote_single_word_translation(self.data)

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

        result = translator._vote_single_word_translation(self.data)

        self.assertIsNone(result)
