"""
What the crawl path does when the LLM answers in the wrong language.

The Aug-2026 bug was silent: Haiku wrote ~half of the summaries for non-English
articles in English, the assessment still succeeded, and the row was stored.
These tests pin the policy that replaced "hope the prompt is strong enough":
ask again once naming the mistake, then drop what is still wrong.

No DB and no network — the LLM is mocked; everything else is real parsing.
"""

from contextlib import contextmanager
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
# Long enough to clear language_check.MIN_CHARS_TO_JUDGE (60), so these two
# exercise the drop path. Real headlines are usually shorter than that and are
# therefore NOT judged — see test_a_short_wrong_language_title_is_not_caught.
DANISH_TITLE = (
    "Regeringen fremlægger nyt klimaforslag om elbiler og indenrigsflyvninger"
)
ENGLISH_TITLE = (
    "Government presents new climate proposal on electric cars and domestic flights"
)
DANISH_BODY = (
    "Regeringen vil gøre det billigere at køre i elbil. Mange partier er enige "
    "i planen. Forslaget skal nu behandles i Folketinget, og det sker efter "
    "sommerferien. Flere eksperter mener, at planen er et vigtigt skridt."
)
ENGLISH_BODY = (
    "The government wants to make it cheaper to drive an electric car. Many "
    "parties agree with the plan. The proposal will now be discussed in "
    "parliament, and that will happen after the summer holidays."
)


@contextmanager
def _llm_returning(response, prompt_function):
    """
    Put the module's whole LLM path under our control: choose a provider without
    needing an API key, use a trivial prompt template, and answer every call with
    `response`. Yields the call mock, so a test can assert how many times we asked
    — which is how "it retried once" is observed.
    """
    with patch.object(
        sac, "_select_provider_and_key", return_value=("anthropic", "fake-key")
    ), patch.object(
        sac, prompt_function, return_value="{title}\n{content}"
    ), patch.object(
        sac, "_call_simplification_llm", return_value=(response, "fake-model")
    ) as llm:
        yield llm


def assessing(response):
    return _llm_returning(response, "get_assessment_and_summary_prompt")


def simplifying(response):
    return _llm_returning(response, "get_adaptive_simplification_prompt")


def an_assessment(summary, level_summary=None, level_title=None):
    """A well-formed assess+summarize response, with the summaries we want to test."""
    response = (
        "ORIGINAL_LEVEL: B1\n"
        "ARTICLE_TYPE: News\n"
        "DISTURBING_CONTENT: NO\n"
        f"ORIGINAL_SUMMARY: {summary}\n"
    )
    if level_title:
        response += f"A2_TITLE: {level_title}\n"
    if level_summary:
        response += f"A2_SUMMARY: {level_summary}\n"
    return response


def a_simplification(body):
    """A well-formed two-level simplification response, with `body` at both levels."""
    return (
        "ORIGINAL_LEVEL: B2\n"
        "ARTICLE_TYPE: News\n"
        "DISTURBING_CONTENT: NO\n"
        f"ORIGINAL_SUMMARY: {DANISH_SUMMARY}\n"
        "SIMPLIFIED_LEVELS: A1, A2\n"
        "A1_TITLE: Nyt klimaforslag\n"
        f"A1_CONTENT: {body}\n"
        f"A1_SUMMARY: {DANISH_SUMMARY}\n"
        "A2_TITLE: Nyt klimaforslag fra regeringen\n"
        f"A2_CONTENT: {body}\n"
        f"A2_SUMMARY: {DANISH_SUMMARY}\n"
    )


class AssessAndSummarizeLanguageTest(TestCase):
    """Policy: ask again once, then drop the summary — the assessment is kept."""

    def test_a_danish_summary_is_kept_and_asked_for_only_once(self):
        with assessing(an_assessment(DANISH_SUMMARY, DANISH_SUMMARY)) as llm:
            result = sac.assess_and_summarize("Titel", "Indhold", "da")

        self.assertEqual(result["original_summary"], DANISH_SUMMARY)
        self.assertIn("A2", result["level_summaries"])
        self.assertEqual(llm.call_count, 1)

    def test_an_english_summary_on_a_danish_article_is_retried_then_dropped(self):
        with assessing(an_assessment(ENGLISH_SUMMARY, ENGLISH_SUMMARY)) as llm:
            result = sac.assess_and_summarize("Titel", "Indhold", "da")

        self.assertEqual(llm.call_count, 2, "should ask again before giving up")
        self.assertEqual(result["original_summary"], "")
        self.assertEqual(result["level_summaries"], {})
        # The assessment has no language of its own, so it survives.
        self.assertEqual(result["original_cefr_level"], "B1")
        self.assertEqual(result["article_type"], "news")

    def test_only_the_wrong_summary_is_dropped(self):
        with assessing(an_assessment(DANISH_SUMMARY, ENGLISH_SUMMARY)):
            result = sac.assess_and_summarize("Titel", "Indhold", "da")

        self.assertEqual(result["original_summary"], DANISH_SUMMARY)
        self.assertEqual(result["level_summaries"], {})

    def test_a_level_title_is_parsed_alongside_its_summary(self):
        with assessing(
            an_assessment(DANISH_SUMMARY, DANISH_SUMMARY, level_title=DANISH_TITLE)
        ):
            result = sac.assess_and_summarize("Titel", "Indhold", "da")

        self.assertEqual(result["level_titles"]["A2"], DANISH_TITLE)
        self.assertEqual(result["level_summaries"]["A2"], DANISH_SUMMARY)

    def test_an_english_level_title_is_dropped_without_costing_its_summary(self):
        """A title and its summary are judged independently: an English headline
        should not take a good Danish summary down with it — the card falls back
        to the article's own title and keeps the level-appropriate blurb."""
        with assessing(
            an_assessment(DANISH_SUMMARY, DANISH_SUMMARY, level_title=ENGLISH_TITLE)
        ):
            result = sac.assess_and_summarize("Titel", "Indhold", "da")

        self.assertEqual(result["level_titles"], {})
        self.assertEqual(result["level_summaries"]["A2"], DANISH_SUMMARY)
        self.assertEqual(result["original_summary"], DANISH_SUMMARY)

    def test_a_short_wrong_language_title_is_not_caught(self):
        """Honest limit, not an aspiration: language_check needs
        MIN_CHARS_TO_JUDGE (60) characters, and most real headlines are shorter,
        so a wrong-language TITLE alone ships. It is a small residual risk because
        one LLM call produces the whole response — an English title almost always
        arrives beside English summaries, which ARE long enough to be judged and
        which trigger the retry. Do not read the drop test above as a guarantee
        that titles are language-guarded in production."""
        with assessing(
            an_assessment(DANISH_SUMMARY, DANISH_SUMMARY, level_title="Climate deal")
        ):
            result = sac.assess_and_summarize("Titel", "Indhold", "da")

        self.assertEqual(result["level_titles"]["A2"], "Climate deal")


class AdaptiveSimplificationLanguageTest(TestCase):
    """Policy: ask again once, then fail the run — nothing is salvaged."""

    def test_a_danish_simplification_is_kept_and_asked_for_only_once(self):
        with simplifying(a_simplification(DANISH_BODY)) as llm:
            result = sac.simplify_article_adaptive_levels("Titel", "Indhold", "da")

        self.assertEqual(result["simplified_levels"], ["A1", "A2"])
        self.assertEqual(llm.call_count, 1)

    def test_an_english_simplification_is_retried_then_fails(self):
        with simplifying(a_simplification(ENGLISH_BODY)) as llm:
            with self.assertRaises(Exception):
                sac.simplify_article_adaptive_levels("Titel", "Indhold", "da")

        self.assertEqual(llm.call_count, 2, "should ask again before giving up")
