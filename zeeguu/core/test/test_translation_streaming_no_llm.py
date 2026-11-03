"""The SSE stream (old app builds only) must not call the LLM: that is
behind the reader's explicit "Ask LLM" (ADR 022)."""

from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.translation_services import translator


def _result(translation, source):
    return {"translation": translation, "source": source, "likelihood": 90}


@patch.object(translator, "translate_with_llm")
@patch.object(translator, "translate_separated_mwe", return_value=_result("calls", "Microsoft - alignment"))
@patch.object(translator, "translate_mwe_phrase", return_value=_result("a farmer", "Google - MWE phrase"))
@patch.object(translator, "deepl_contextual_translate_cached", return_value=_result("a pawn", "DeepL"))
@patch.object(translator, "google_contextual_translate", return_value=None)
@patch.object(translator, "microsoft_contextual_translate", return_value=None)
@patch.object(translator, "azure_alignment_contextual_translate", return_value=None)
class StreamingNoLlmTest(TestCase):

    def test_a_phrase_streams_providers_only(self, azure, ms, google, deepl, phrase, separated, llm):
        streamed = list(translator.get_translations_streaming(
            "en bonde", "For jeg' en bonde i et kongespil", "da", "en"))

        self.assertEqual([t["translation"] for t in streamed][:1], ["a farmer"])
        self.assertIn("a pawn", [t["translation"] for t in streamed])
        llm.assert_not_called()

    def test_a_separated_mwe_streams_providers_only(self, azure, ms, google, deepl, phrase, separated, llm):
        streamed = list(translator.get_translations_streaming(
            "ruft ... an", "Er ruft mich morgen an", "de", "en",
            is_separated_mwe=True, full_sentence_context="Er ruft mich morgen an"))

        self.assertEqual([t["translation"] for t in streamed], ["calls"])
        llm.assert_not_called()
