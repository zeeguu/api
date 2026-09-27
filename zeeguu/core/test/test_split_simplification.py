from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.llm_services import simplification_and_classification as sc
from zeeguu.core.llm_services.prompts.split_simplification import (
    get_split_level_prompt,
    rare_words,
)

TITLE = "Scientists map the brain cells behind depression"
CONTENT = (
    "Researchers have identified the microglia and excitatory neurons involved in depression.\n\n"
    "The findings, published in Nature Genetics, offer clues for targeted therapies.\n\n"
    "Depression affects more than 264 million people worldwide."
)

ASSESSMENT = """DISTURBING_CONTENT: NO

ARTICLE_TYPE: GENERAL

ORIGINAL_LEVEL: B2

ORIGINAL_SUMMARY: Researchers found the **brain cells** linked to depression."""


def level_response(level, with_content_label=True):
    return (
        f"TITLE: {level} title\n"
        f"SUMMARY: {level} summary\n"
        + ("CONTENT:\n" if with_content_label else "")
        + f"[1] {level} one.\n\n[2] {level} two.\n\n[3] {level} three."
    )


class FakeLLM:
    """Stands in for sc._complete: answers by prompt type, records (provider, prompt)."""

    def __init__(self, assessment=ASSESSMENT, fail=(), with_content_label=True):
        self.assessment = assessment
        self.fail = set(fail)  # providers, or (provider, level) pairs, that raise
        self.with_content_label = with_content_label
        self.calls = []

    def __call__(self, provider, prompt, max_tokens):
        self.calls.append((provider, prompt))
        if "Assess this" in prompt:
            if provider in self.fail:
                raise Exception(f"{provider} down")
            return self.assessment
        level = prompt.split("at CEFR level ")[1][:2]
        if provider in self.fail or (provider, level) in self.fail:
            raise Exception(f"{provider} down")
        return level_response(level, self.with_content_label)


def simplify(llm, **kwargs):
    with patch.object(sc, "_complete", llm):
        return sc.simplify_article_adaptive_levels(TITLE, CONTENT, "en", **kwargs)


class SplitSimplificationTest(TestCase):
    def test_creates_all_levels_below_the_original(self):
        result = simplify(FakeLLM())

        self.assertEqual(result["original_cefr_level"], "B2")
        self.assertEqual(result["simplified_levels"], ["A1", "A2", "B1"])
        self.assertEqual(result["article_type"], "general")
        self.assertFalse(result["is_disturbing"])
        self.assertEqual(result["original_summary"], "Researchers found the brain cells linked to depression.")
        self.assertEqual(result["model_name"], "deepseek-chat")

        a2 = result["versions"]["A2"]
        self.assertEqual(a2["title"], "A2 title")
        self.assertEqual(a2["summary"], "A2 summary")
        self.assertEqual(a2["content"], "A2 one.\n\nA2 two.\n\nA2 three.")
        self.assertEqual(a2["model_name"], "deepseek-chat")

    def test_parses_levels_without_content_label(self):
        result = simplify(FakeLLM(with_content_label=False))

        self.assertEqual(result["versions"]["A1"]["content"], "A1 one.\n\nA1 two.\n\nA1 three.")
        self.assertEqual(result["versions"]["A1"]["summary"], "A1 summary")

    def test_parses_numbered_paragraphs_on_consecutive_lines(self):
        version = sc._parse_level("TITLE: t\nSUMMARY: s\nCONTENT:\n[1] one.\n[2] two.\n[3] three.", 3)

        self.assertEqual(version["content"], "one.\n\ntwo.\n\nthree.")

    def test_truncated_haiku_reply_is_a_failure(self):
        truncated = type("Response", (), {
            "status_code": 200,
            "json": lambda self: {"stop_reason": "max_tokens", "content": [{"text": "TITLE: cut"}]},
        })()
        with patch("zeeguu.core.llm_services.haiku_client._post", return_value=truncated):
            with self.assertRaises(Exception):
                sc._complete("anthropic", "prompt", 10)

    def test_deepseek_gets_the_strict_prompt(self):
        llm = FakeLLM()
        simplify(llm)

        level_prompts = [p for provider, p in llm.calls if "at CEFR level" in p]
        self.assertEqual(len(level_prompts), 3)
        self.assertTrue(all("HARD" in p and "WORDS TO AVOID" in p for p in level_prompts))

    def test_falls_back_to_anthropic_with_the_non_strict_prompt(self):
        llm = FakeLLM(fail={("deepseek", "A2")})
        result = simplify(llm)

        self.assertEqual(result["versions"]["A1"]["model_name"], "deepseek-chat")
        self.assertEqual(result["versions"]["A2"]["model_name"], sc.HAIKU_MODEL)
        anthropic_prompt = next(p for provider, p in llm.calls if provider == "anthropic")
        self.assertNotIn("WORDS TO AVOID", anthropic_prompt)

    def test_falls_back_for_the_assessment_too(self):
        result = simplify(FakeLLM(fail={"deepseek"}))

        self.assertEqual(result["simplified_levels"], ["A1", "A2", "B1"])
        self.assertEqual(result["provider"], "anthropic")

    def test_skips_a_level_that_fails_everywhere(self):
        result = simplify(FakeLLM(fail={("deepseek", "B1"), ("anthropic", "B1")}))

        self.assertEqual(result["simplified_levels"], ["A1", "A2"])

    def test_fails_when_no_level_can_be_created(self):
        with self.assertRaises(Exception):
            simplify(FakeLLM(fail={(p, l) for p in sc.PROVIDERS for l in ("A1", "A2", "B1")}))

    def test_paywalled_article_is_rejected_without_fallback(self):
        llm = FakeLLM(assessment="unfinished")
        with self.assertRaises(Exception) as ctx:
            simplify(llm)

        self.assertIn("PAYWALL", str(ctx.exception))
        self.assertEqual(len(llm.calls), 1)

    def test_advertorial_is_rejected(self):
        with self.assertRaises(Exception) as ctx:
            simplify(FakeLLM(assessment="Advertorial."))

        self.assertIn("ADVERTORIAL", str(ctx.exception))

    def test_a1_original_needs_no_versions(self):
        result = simplify(FakeLLM(assessment=ASSESSMENT.replace("B2", "A1")))

        self.assertEqual(result["simplified_levels"], [])
        self.assertEqual(result["versions"], {})

    def test_unknown_level_defaults_to_b2(self):
        result = simplify(FakeLLM(assessment=ASSESSMENT.replace("B2", "X9")))

        self.assertEqual(result["original_cefr_level"], "B2")
        self.assertEqual(result["simplified_levels"], ["A1", "A2", "B1"])


class SplitPromptTest(TestCase):
    def test_numbers_the_original_paragraphs(self):
        prompt = get_split_level_prompt("en", TITLE, CONTENT, "A2")

        self.assertIn("Output exactly 3 paragraphs", prompt)
        self.assertIn("[1] Researchers have identified", prompt)
        self.assertIn("[3] Depression affects", prompt)

    def test_rare_words_skip_names_and_common_words(self):
        words = rare_words(CONTENT, "en", "A2")

        self.assertIn("microglia", words)
        self.assertIn("excitatory", words)
        self.assertNotIn("Nature", words)
        self.assertNotIn("people", words)

    def test_rare_words_for_unsupported_language_is_empty(self):
        self.assertEqual(rare_words(CONTENT, "xx", "A2"), [])
