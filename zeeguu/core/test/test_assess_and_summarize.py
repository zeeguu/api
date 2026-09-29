"""Regression tests for assess_and_summarize: article_type handling, and how an
article gets rejected as junk.

The article.article_type column is enum('news','general') with a case-sensitive
utf8mb4_bin collation. If the parser returns an UPPERCASE 'NEWS'/'GENERAL', the
crawl-time assessment write fails with "Data truncated for column 'article_type'"
and the whole assessment (cefr_level, summary, type) rolls back — silently
starving level-filtered feeds. These tests pin the returned value to lowercase.

See: on-demand simplification path in
zeeguu/core/llm_services/simplification_and_classification.py
"""
from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.llm_services import simplification_and_classification as sac


def _mock_llm_response(article_type_line):
    """A minimal well-formed assessment response with the given ARTICLE_TYPE line."""
    return (
        "ORIGINAL_LEVEL: B1\n"
        f"{article_type_line}\n"
        "ORIGINAL_SUMMARY: A short summary of the article.\n"
        "DISTURBING_CONTENT: NO\n"
    )


class AssessAndSummarizeArticleTypeTest(TestCase):
    def _run(self, article_type_line):
        with patch.object(
            sac, "_select_provider_and_key", return_value=("anthropic", "fake-key")
        ), patch.object(
            sac, "get_assessment_and_summary_prompt", return_value="{title}\n{content}"
        ), patch.object(
            sac,
            "_call_simplification_llm",
            return_value=(_mock_llm_response(article_type_line), "fake-model"),
        ):
            return sac.assess_and_summarize("Title", "Body content", "da")

    def test_news_is_lowercased_for_the_enum(self):
        # Must be a valid enum('news','general') member — never uppercase.
        self.assertEqual(self._run("ARTICLE_TYPE: News")["article_type"], "news")

    def test_general_is_lowercased_for_the_enum(self):
        self.assertEqual(self._run("ARTICLE_TYPE: GENERAL")["article_type"], "general")

    def test_unrecognized_article_type_is_none(self):
        self.assertIsNone(self._run("ARTICLE_TYPE: Editorial")["article_type"])

    def test_missing_article_type_is_none(self):
        # No ARTICLE_TYPE line at all -> None, not an empty/invalid string.
        with patch.object(
            sac, "_select_provider_and_key", return_value=("anthropic", "fake-key")
        ), patch.object(
            sac, "get_assessment_and_summary_prompt", return_value="{title}\n{content}"
        ), patch.object(
            sac,
            "_call_simplification_llm",
            return_value=(
                "ORIGINAL_LEVEL: B1\nORIGINAL_SUMMARY: x\nDISTURBING_CONTENT: NO\n",
                "fake-model",
            ),
        ):
            self.assertIsNone(sac.assess_and_summarize("T", "C", "da")["article_type"])


class AssessAndSummarizeRejectionTest(TestCase):
    """How an article is rejected as junk.

    The prompt used to offer a bare one-word reply ("unfinished") as the ONLY
    way to report a paywall, which let a model end the whole response with one
    token. deepseek-chat took that exit on 100% of articles — including complete
    ones — which read as a broken model for weeks. The signal is a field now;
    the bare word is still honoured for any model that ignores the change.
    """

    def _assess(self, llm_response):
        with patch.object(
            sac, "_select_provider_and_key", return_value=("anthropic", "fake-key")
        ), patch.object(
            sac, "get_assessment_and_summary_prompt", return_value="{title}\n{content}"
        ), patch.object(
            sac, "_call_simplification_llm", return_value=(llm_response, "fake-model")
        ):
            return sac.assess_and_summarize("Titel", "Indhold", "da")

    def test_the_incomplete_field_rejects_the_article(self):
        """The paywall signal is a field now, not a bare one-word reply — it must
        still reject. (The bare word kept working too; see
        test_a_bare_unfinished_still_rejects.)"""
        response = (
            "INCOMPLETE_ARTICLE: YES\n"
            "ADVERTORIAL_CONTENT: NO\n"
            "DISTURBING_CONTENT: NO\n"
            "ARTICLE_TYPE: News\n"
            "ORIGINAL_LEVEL: B1\n"
            "ORIGINAL_SUMMARY: Noget dansk tekst her.\n"
        )
        with self.assertRaises(Exception) as raised:
            self._assess(response)
        assert str(raised.exception).startswith("PAYWALL")

    def test_the_advertorial_field_rejects_the_article(self):
        response = (
            "INCOMPLETE_ARTICLE: NO\n"
            "ADVERTORIAL_CONTENT: YES\n"
            "DISTURBING_CONTENT: NO\n"
            "ARTICLE_TYPE: General\n"
            "ORIGINAL_LEVEL: B1\n"
            "ORIGINAL_SUMMARY: Noget dansk tekst her.\n"
        )
        with self.assertRaises(Exception) as raised:
            self._assess(response)
        assert str(raised.exception).startswith("ADVERTORIAL")

    def test_a_bare_unfinished_still_rejects(self):
        """Backward compatibility: the prompt no longer offers the bare word, but a
        model that answers with it anyway must not be parsed into an empty
        assessment."""
        with self.assertRaises(Exception) as raised:
            self._assess("unfinished")
        assert str(raised.exception).startswith("PAYWALL")

    def test_a_clean_article_is_not_rejected_when_the_flags_are_absent(self):
        """Rows from a model that omits the new fields entirely must default to
        NO — absent must never read as "junk", or every such article is dropped."""
        response = (
            "DISTURBING_CONTENT: NO\n"
            "ARTICLE_TYPE: News\n"
            "ORIGINAL_LEVEL: B1\n"
            "ORIGINAL_SUMMARY: Regeringen har fremlagt et nyt forslag om klimaet i dag.\n"
        )
        assert self._assess(response)["original_cefr_level"] == "B1"


class StopOnRejectionTest(TestCase):
    """A rejected article used to be written out in full — every level's title and
    summary — and then thrown away. The call now stops on the first YES flag;
    these pin that a reply cut short there still rejects, and that a normal
    reply is never mistaken for one."""

    def _assess(self, llm_response):
        with patch.object(
            sac, "_select_provider_and_key", return_value=("anthropic", "fake-key")
        ), patch.object(
            sac, "get_assessment_and_summary_prompt", return_value="{title}\n{content}"
        ), patch.object(
            sac, "_call_simplification_llm", return_value=(llm_response, "fake-model")
        ) as call:
            try:
                return sac.assess_and_summarize("Titel", "Indhold", "da")
            finally:
                assert call.call_args.kwargs["stop"] == sac.REJECTION_STOPS

    def test_a_reply_cut_at_the_incomplete_flag_rejects_as_paywall(self):
        with self.assertRaises(Exception) as raised:
            self._assess("INCOMPLETE_ARTICLE: YES")
        assert str(raised.exception).startswith("PAYWALL")

    def test_a_reply_cut_at_the_advertorial_flag_rejects_as_advertorial(self):
        with self.assertRaises(Exception) as raised:
            self._assess("INCOMPLETE_ARTICLE: NO\n\nADVERTORIAL_CONTENT: YES")
        assert str(raised.exception).startswith("ADVERTORIAL")


class DeepseekStopThatFiredTest(TestCase):
    """DeepSeek strips the matched stop and reports finish_reason "stop" either
    way, so which flag fired is inferred from the text that is left."""

    def _fired(self, result, finish_reason="stop", stop=sac.REJECTION_STOPS):
        return sac._deepseek_stop_that_fired(result, finish_reason, stop)

    def test_nothing_written_means_the_incomplete_flag(self):
        assert self._fired("") == sac.INCOMPLETE_STOP

    def test_incomplete_written_means_the_advertorial_flag(self):
        assert self._fired("INCOMPLETE_ARTICLE: NO") == sac.ADVERTORIAL_STOP

    def test_a_complete_reply_is_not_a_stop(self):
        full = "INCOMPLETE_ARTICLE: NO\nADVERTORIAL_CONTENT: NO\nORIGINAL_LEVEL: B1"
        assert self._fired(full) is None

    def test_running_out_of_tokens_is_not_a_stop(self):
        assert self._fired("INCOMPLETE_ARTICLE: NO", finish_reason="length") is None

    def test_no_stop_sequences_means_no_stop(self):
        assert self._fired("", stop=None) is None


class HaikuStopSequenceTest(TestCase):
    """Anthropic strips the matched stop sequence; the client puts it back so the
    caller parses the flag the model actually wrote."""

    def _complete(self, payload):
        from zeeguu.core.llm_services import haiku_client

        response = type(
            "R", (), {"status_code": 200, "json": lambda self: payload, "text": ""}
        )()
        with patch.dict("os.environ", {"ANTHROPIC_TEXT_SIMPLIFICATION_KEY": "k"}), patch.object(
            haiku_client.requests, "post", return_value=response
        ) as post:
            text = haiku_client.haiku_completion_or_raise(
                "p", max_tokens=10, stop_sequences=sac.REJECTION_STOPS
            )
        assert post.call_args.kwargs["json"]["stop_sequences"] == sac.REJECTION_STOPS
        return text

    def test_the_matched_sequence_is_put_back(self):
        text = self._complete(
            {
                "content": [{"type": "text", "text": "INCOMPLETE_ARTICLE: NO\n\n"}],
                "stop_reason": "stop_sequence",
                "stop_sequence": sac.ADVERTORIAL_STOP,
            }
        )
        assert text.endswith(sac.ADVERTORIAL_STOP)

    def test_a_stop_on_the_first_token_has_no_content_block(self):
        text = self._complete(
            {
                "content": [],
                "stop_reason": "stop_sequence",
                "stop_sequence": sac.INCOMPLETE_STOP,
            }
        )
        assert text == sac.INCOMPLETE_STOP

    def test_a_normal_ending_is_untouched(self):
        text = self._complete(
            {
                "content": [{"type": "text", "text": "ORIGINAL_LEVEL: B1"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
            }
        )
        assert text == "ORIGINAL_LEVEL: B1"
