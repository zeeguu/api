"""
What the crawl/simplification path does when the LLM answers in the wrong language.

The Aug-2026 bug was silent: Haiku wrote ~half of the summaries for non-English
articles in English, the assessment still succeeded, and the row was stored. These
tests pin the policy that replaced "hope the prompt is strong enough" — re-ask
once naming the mistake, then drop only what is still wrong.

No DB: the LLM call is mocked, everything else is parsing and policy.
"""

from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.llm_services import simplification_and_classification as sac

DANISH_SUMMARY = (
    "Regeringen har fremlagt et nyt forslag om klimaet, som skal gøre det "
    "billigere at køre i elbil og dyrere at flyve inden for landets grænser."
)

ENGLISH_SUMMARY = (
    "The government has presented a new climate proposal that would make it "
    "cheaper to drive an electric car and more expensive to fly within the country."
)

DANISH_BODY = (
    "Regeringen vil gøre det billigere at køre i elbil. Mange partier er enige "
    "i planen. Forslaget skal nu behandles i Folketinget, og det sker efter "
    "sommerferien. Flere eksperter mener, at planen er et vigtigt skridt for "
    "klimaet i Danmark."
)

ENGLISH_BODY = (
    "The government wants to make it cheaper to drive an electric car. Many "
    "parties agree with the plan. The proposal will now be discussed in "
    "parliament, and that will happen after the summer holidays. Experts say "
    "the plan is an important step for the climate in Denmark."
)


def _assessment(summary, level_summary=None):
    response = (
        "ORIGINAL_LEVEL: B1\n"
        "ARTICLE_TYPE: News\n"
        "DISTURBING_CONTENT: NO\n"
        f"ORIGINAL_SUMMARY: {summary}\n"
    )
    if level_summary:
        response += f"A2_SUMMARY: {level_summary}\n"
    return response


class AssessAndSummarizeLanguageTest(TestCase):
    """Policy: retry once, then drop the summary — the assessment is kept."""

    def _run(self, response):
        with patch.object(
            sac, "_select_provider_and_key", return_value=("anthropic", "fake-key")
        ), patch.object(
            sac, "get_assessment_and_summary_prompt", return_value="{title}\n{content}"
        ), patch.object(
            sac, "_call_simplification_llm", return_value=(response, "fake-model")
        ) as call:
            return sac.assess_and_summarize("Titel", "Indhold", "da"), call

    def test_a_danish_summary_is_kept_and_asked_for_only_once(self):
        result, call = self._run(_assessment(DANISH_SUMMARY, DANISH_SUMMARY))
        self.assertEqual(result["original_summary"], DANISH_SUMMARY)
        self.assertIn("A2", result["level_summaries"])
        self.assertEqual(call.call_count, 1)

    def test_an_english_summary_on_a_danish_article_is_retried_then_dropped(self):
        result, call = self._run(_assessment(ENGLISH_SUMMARY, ENGLISH_SUMMARY))
        self.assertEqual(call.call_count, 2, "should re-ask once before giving up")
        self.assertEqual(result["original_summary"], "")
        self.assertEqual(result["level_summaries"], {})
        # The assessment is language-independent and survives.
        self.assertEqual(result["original_cefr_level"], "B1")
        self.assertEqual(result["article_type"], "news")

    def test_only_the_wrong_summary_is_dropped(self):
        result, _ = self._run(_assessment(DANISH_SUMMARY, ENGLISH_SUMMARY))
        self.assertEqual(result["original_summary"], DANISH_SUMMARY)
        self.assertEqual(result["level_summaries"], {})


def _simplification(a1_body, a2_body):
    return (
        "ORIGINAL_LEVEL: B2\n"
        "ARTICLE_TYPE: News\n"
        "DISTURBING_CONTENT: NO\n"
        f"ORIGINAL_SUMMARY: {DANISH_SUMMARY}\n"
        "SIMPLIFIED_LEVELS: A1, A2\n"
        "A1_TITLE: Nyt klimaforslag\n"
        f"A1_CONTENT: {a1_body}\n"
        f"A1_SUMMARY: {DANISH_SUMMARY}\n"
        "A2_TITLE: Nyt klimaforslag fra regeringen\n"
        f"A2_CONTENT: {a2_body}\n"
        f"A2_SUMMARY: {DANISH_SUMMARY}\n"
    )


class AdaptiveSimplificationLanguageTest(TestCase):
    """Policy: retry once, then drop that level — the good levels are kept."""

    def _run(self, response):
        with patch.object(
            sac, "_select_provider_and_key", return_value=("deepseek", "fake-key")
        ), patch.object(
            sac, "get_adaptive_simplification_prompt", return_value="{title}\n{content}"
        ), patch.object(
            sac, "_call_simplification_llm", return_value=(response, "fake-model")
        ) as call:
            return (
                sac.simplify_article_adaptive_levels("Titel", "Indhold", "da"),
                call,
            )

    def test_all_danish_levels_are_kept(self):
        result, call = self._run(_simplification(DANISH_BODY, DANISH_BODY))
        self.assertEqual(result["simplified_levels"], ["A1", "A2"])
        self.assertEqual(call.call_count, 1)

    def test_an_english_level_is_dropped_and_the_danish_one_survives(self):
        result, call = self._run(_simplification(DANISH_BODY, ENGLISH_BODY))
        self.assertEqual(call.call_count, 2, "should re-ask once before giving up")
        self.assertEqual(result["simplified_levels"], ["A1"])
        self.assertEqual(list(result["versions"]), ["A1"])

    def test_a_run_with_no_surviving_level_fails(self):
        with self.assertRaises(Exception):
            self._run(_simplification(ENGLISH_BODY, ENGLISH_BODY))
