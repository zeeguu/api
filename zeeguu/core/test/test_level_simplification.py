"""
SimplificationService.simplify_text: one CEFR level per call, DeepSeek first with
the strict prompt, Haiku as the fallback with the plain one.

No DB and no network: the two completions are faked; prompts, parsing and the
output-language check are real.
"""

from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.llm_services import models
from zeeguu.core.llm_services.haiku_client import HAIKU_MODEL
from zeeguu.core.llm_services.prompts.level_simplification import (
    get_level_simplification_prompt,
    paragraphs,
    rare_words,
)
from zeeguu.core.llm_services.simplification_service import (
    SimplificationService,
    parse_level_reply,
)

TITLE = "Scientists map the brain cells behind depression"
CONTENT = (
    "Researchers have identified the microglia and excitatory neurons involved in depression.\n\n"
    "The findings, published in Nature Genetics, offer clues for targeted therapies.\n\n"
    "Depression affects more than 264 million people worldwide."
)

DANISH_TITLE = "Regeringen vil gøre elbiler billigere"
DANISH_BODY = (
    "Regeringen vil gøre det billigere at køre i elbil. Mange partier er enige "
    "i planen. Forslaget skal nu behandles i Folketinget efter sommerferien."
)
ENGLISH_BODY = (
    "The government wants to make it cheaper to drive an electric car. Many "
    "parties agree with the plan. Parliament will discuss it after the summer."
)


def level_reply(level, with_content_label=True):
    return (
        f"TITLE: {level} title\n"
        f"SUMMARY: {level} summary\n"
        + ("CONTENT:\n" if with_content_label else "")
        + f"[1] {level} one.\n\n[2] {level} two.\n\n[3] {level} three."
    )


class FakeProviders:
    """Stands in for both completions; records (provider, prompt)."""

    def __init__(self, deepseek=None, haiku=None):
        self.replies = {"deepseek": deepseek, "haiku": haiku}
        self.calls = []

    def complete(self, provider):
        def call(prompt):
            self.calls.append((provider, prompt))
            reply = self.replies[provider]
            if isinstance(reply, Exception):
                raise reply
            return reply

        return call

    def prompts(self, provider):
        return [p for name, p in self.calls if name == provider]


def simplify(fake, level="A2", title=TITLE, content=CONTENT, language="en"):
    service = SimplificationService()
    service.deepseek_api_key = "fake"
    service.anthropic_api_key = "fake"
    with patch.object(service, "_complete_deepseek", fake.complete("deepseek")), patch.object(
        service, "_complete_haiku", fake.complete("haiku")
    ):
        return service.simplify_text(title, content, level, language)


class SimplifyTextTest(TestCase):
    def test_deepseek_writes_the_level_with_the_strict_prompt(self):
        fake = FakeProviders(deepseek=level_reply("A2"))
        result = simplify(fake)

        self.assertEqual(result["title"], "A2 title")
        self.assertEqual(result["summary"], "A2 summary")
        self.assertEqual(result["content"].count("<p>"), 3)
        self.assertIn("A2 two.", result["content"])
        self.assertEqual(result["model_name"], models.DEEPSEEK_GENERAL)
        prompt = fake.prompts("deepseek")[0]
        self.assertIn("HARD A2 LIMITS", prompt)
        self.assertIn("WORDS TO AVOID", prompt)
        self.assertEqual(fake.prompts("haiku"), [])

    def test_falls_back_to_haiku_with_the_plain_prompt(self):
        fake = FakeProviders(deepseek=Exception("DeepSeek API error: 402"), haiku=level_reply("B1"))
        result = simplify(fake, level="B1")

        self.assertEqual(result["title"], "B1 title")
        self.assertEqual(result["model_name"], HAIKU_MODEL)
        prompt = fake.prompts("haiku")[0]
        self.assertIn("at CEFR level B1", prompt)
        self.assertNotIn("HARD", prompt)
        self.assertNotIn("WORDS TO AVOID", prompt)

    def test_an_unparseable_deepseek_reply_falls_back(self):
        fake = FakeProviders(deepseek="Sorry, I cannot help with that.", haiku=level_reply("A1"))

        self.assertEqual(simplify(fake, level="A1")["model_name"], HAIKU_MODEL)

    def test_a_wrong_language_deepseek_reply_falls_back_after_one_retry(self):
        english = f"TITLE: {DANISH_TITLE}\nSUMMARY: Elbiler bliver billigere.\nCONTENT:\n[1] {ENGLISH_BODY}"
        danish = f"TITLE: {DANISH_TITLE}\nSUMMARY: Elbiler bliver billigere.\nCONTENT:\n[1] {DANISH_BODY}"
        fake = FakeProviders(deepseek=english, haiku=danish)
        result = simplify(fake, title=DANISH_TITLE, content=DANISH_BODY, language="da")

        self.assertEqual(len(fake.prompts("deepseek")), 2)
        self.assertEqual(result["model_name"], HAIKU_MODEL)
        self.assertIn("Folketinget", result["content"])

    def test_none_when_every_provider_fails(self):
        fake = FakeProviders(deepseek=Exception("down"), haiku=None)

        self.assertIsNone(simplify(fake))

    def test_skips_a_provider_without_a_key(self):
        fake = FakeProviders(haiku=level_reply("A2"))
        service = SimplificationService()
        service.deepseek_api_key = None
        service.anthropic_api_key = "fake"
        with patch.object(service, "_complete_haiku", fake.complete("haiku")):
            result = service.simplify_text(TITLE, CONTENT, "A2", "en")

        self.assertEqual(result["model_name"], HAIKU_MODEL)
        self.assertEqual(fake.prompts("deepseek"), [])


class ParseLevelReplyTest(TestCase):
    def test_parses_title_summary_and_numbered_paragraphs(self):
        version = parse_level_reply(level_reply("A2"), 3)

        self.assertEqual(version["content"], "A2 one.\n\nA2 two.\n\nA2 three.")
        self.assertEqual(version["summary"], "A2 summary")

    def test_parses_a_reply_without_the_content_label(self):
        # DeepSeek sometimes starts straight with the numbered paragraphs
        version = parse_level_reply(level_reply("A1", with_content_label=False), 3)

        self.assertEqual(version["content"], "A1 one.\n\nA1 two.\n\nA1 three.")
        self.assertEqual(version["summary"], "A1 summary")

    def test_parses_numbered_paragraphs_on_consecutive_lines(self):
        version = parse_level_reply("TITLE: t\nSUMMARY: s\nCONTENT:\n[1] one.\n[2] two.\n[3] three.", 3)

        self.assertEqual(version["content"], "one.\n\ntwo.\n\nthree.")

    def test_strips_markdown_from_the_summary(self):
        version = parse_level_reply("TITLE: t\nSUMMARY: The **brain** cells\nCONTENT:\n[1] one.", 1)

        self.assertEqual(version["summary"], "The brain cells")

    def test_a_reply_missing_a_part_is_an_error(self):
        with self.assertRaises(Exception):
            parse_level_reply("TITLE: t\nCONTENT:\n[1] one.", 1)


class LevelPromptTest(TestCase):
    def test_numbers_the_original_paragraphs(self):
        prompt = get_level_simplification_prompt("en", TITLE, CONTENT, "A2")

        self.assertIn("Output exactly 3 paragraphs", prompt)
        self.assertIn("[1] Researchers have identified", prompt)
        self.assertIn("[3] Depression affects", prompt)

    def test_rare_words_skip_names_and_common_words(self):
        words = rare_words(CONTENT, "en", "A2")

        self.assertIn("microglia", words)
        self.assertIn("excitatory", words)
        self.assertNotIn("Nature", words)
        self.assertNotIn("people", words)

    def test_rare_words_work_for_small_wordlist_languages(self):
        # Danish only has wordfreq's small list; words it doesn't know are skipped on purpose
        words = rare_words("Retten udsatte domsafsigelsen i retssagen mod den anklagede til i morgen.", "da", "A2")

        self.assertIn("retssagen", words)
        self.assertIn("anklagede", words)
        self.assertNotIn("domsafsigelsen", words)
        self.assertNotIn("morgen", words)

    def test_rare_words_skip_elisions_and_names_after_them(self):
        words = rare_words("C’est d’abord l’Insead qui a publié l’étude.", "fr", "A2")

        self.assertNotIn("C’est", words)
        self.assertNotIn("d’abord", words)
        self.assertNotIn("l’Insead", words)

    def test_rare_words_skip_unknown_capitalized_words_in_german(self):
        words = rare_words("Marius Borg Høiby stand wegen Körperverletzung vor Gericht.", "de", "A2")

        self.assertNotIn("Høiby", words)
        self.assertIn("Körperverletzung", words)

    def test_rare_words_for_unsupported_language_is_empty(self):
        self.assertEqual(rare_words(CONTENT, "xx", "A2"), [])

    def test_blank_lines_separate_paragraphs(self):
        self.assertEqual(paragraphs("A.\n\nB\nstill B.\n\nC."), ["A.", "B\nstill B.", "C."])

    def test_single_newlines_separate_paragraphs_when_there_are_no_blank_lines(self):
        # pasted texts and ~1 in 7 uploads; wrapped lines (from a PDF) are joined
        text = "First paragraph ends here.\nSecond one is wrapped\nacross two lines.\nThird: «quote»\nFourth"
        self.assertEqual(
            paragraphs(text),
            ["First paragraph ends here.", "Second one is wrapped across two lines.", "Third: «quote»", "Fourth"],
        )
        self.assertIn("Output exactly 4 paragraphs", get_level_simplification_prompt("en", TITLE, text, "A2"))


    def test_short_lines_stay_paragraphs(self):
        # headings and list items in a pasted text are not line wrapping
        self.assertEqual(
            paragraphs("Ingredients\nFlour\nSugar\nHow to do it\nMix it all together."),
            ["Ingredients", "Flour", "Sugar", "How to do it", "Mix it all together."],
        )


class RareWordsSourceTest(TestCase):
    def test_avoid_lists_are_the_evaluated_ones(self):
        # #773 evaluated lists computed with wordfreq; wordstats serves the same
        # frequencies from disk, and the lists must come out identical
        import wordfreq

        from zeeguu.core.llm_services.prompts import level_simplification as ls

        text = "Retten udsatte domsafsigelsen i retssagen mod den anklagede til i morgen. " + DANISH_BODY
        expected = {}
        for word in ls.WORD.findall(text):
            if not word[0].isupper():
                zipf = wordfreq.zipf_frequency(word.lower(), "da")
                if 0 < zipf < ls.RARE_WORD_ZIPF["A2"]:
                    expected[word] = zipf
        self.assertEqual(rare_words(text, "da", "A2"), sorted(expected, key=expected.get))


class TextWithParagraphsTest(TestCase):
    """Readability's textContent glues paragraphs; the HTML still has them."""

    HTML = (
        '<div><p>Efter at have analyseret data er de ikke i tvivl.</p>'
        "<section><p>I den heftige debat er der to <b>fløje</b>.</p></section>"
        "<ul><li><p>Den første fløj.</p></li><li>Den anden fløj.</li></ul></div>"
    )
    GLUED = "Efter at have analyseret data er de ikke i tvivl.I den heftige debat er der to fløje.Den første fløj.Den anden fløj."

    def test_glued_text_gets_the_htmls_paragraphs(self):
        from zeeguu.core.llm_services.prompts.level_simplification import text_with_paragraphs

        self.assertEqual(
            paragraphs(text_with_paragraphs(self.GLUED, self.HTML)),
            [
                "Efter at have analyseret data er de ikke i tvivl.",
                "I den heftige debat er der to fløje.",
                "Den første fløj.",
                "Den anden fløj.",
            ],
        )

    def test_text_with_line_breaks_is_kept(self):
        from zeeguu.core.llm_services.prompts.level_simplification import text_with_paragraphs

        text = "First.\n\nSecond."
        self.assertEqual(text_with_paragraphs(text, self.HTML), text)

    def test_without_html_the_text_is_kept(self):
        from zeeguu.core.llm_services.prompts.level_simplification import text_with_paragraphs

        self.assertEqual(text_with_paragraphs(self.GLUED, None), self.GLUED)
        self.assertEqual(text_with_paragraphs(self.GLUED, "<p>Only one block.</p>"), self.GLUED)

    def test_html_missing_much_of_the_text_is_not_used(self):
        from zeeguu.core.llm_services.prompts.level_simplification import text_with_paragraphs

        partial = "<p>Efter at have analyseret data.</p><p>Kort.</p>"
        self.assertEqual(text_with_paragraphs(self.GLUED, partial), self.GLUED)
