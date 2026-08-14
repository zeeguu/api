"""Regression tests for assess_and_summarize's article_type handling.

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
