"""
SimplificationService.simplify_text: one CEFR level per call, DeepSeek first with
the strict prompt, Haiku as the fallback with the plain one. And translate_and_adapt,
which translates (Google, else DeepSeek, else Haiku) and then calls simplify_text.

No DB and no network: the two completions, Google and the DeepL client are faked; prompts, parsing and the
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
        def call(prompt, max_tokens=None, timeout=None):
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


class TranslateAndAdaptTest(TestCase):
    """translate_and_adapt: a full translation (Google, else an LLM), then simplify_text."""

    def _service(self):
        service = SimplificationService()
        service.deepseek_api_key = "fake"
        service.anthropic_api_key = "fake"
        return service

    def _translate(self, fake, google=None):
        service = self._service()
        with patch(
            "zeeguu.core.llm_services.simplification_service.google_translate_article", return_value=google
        ), patch.object(service, "_complete_deepseek", fake.complete("deepseek")), patch.object(
            service, "_complete_haiku", fake.complete("haiku")
        ):
            return service.translate(TITLE, "## Heading\n\n" + ENGLISH_BODY, "en", "da")

    def test_google_translates_and_no_llm_is_asked(self):
        fake = FakeProviders()
        google = {"title": DANISH_TITLE, "content": DANISH_BODY}

        self.assertEqual(self._translate(fake, google=google), google)
        self.assertEqual(fake.calls, [])

    def test_google_in_the_wrong_language_falls_back_to_deepseek(self):
        fake = FakeProviders(deepseek=f"TITLE: {DANISH_TITLE}\nCONTENT:\n{DANISH_BODY}")
        result = self._translate(fake, google={"title": TITLE, "content": ENGLISH_BODY})

        self.assertEqual(len(fake.prompts("deepseek")), 1)
        self.assertEqual(result["content"], DANISH_BODY)

    def test_without_google_deepseek_translates_with_the_structure_and_title_rules(self):
        fake = FakeProviders(deepseek=f"TITLE: {DANISH_TITLE}\n\n## Overskrift\n\n{DANISH_BODY}")
        result = self._translate(fake)

        self.assertEqual(result, {"title": DANISH_TITLE, "content": f"## Overskrift\n\n{DANISH_BODY}"})
        prompt = fake.prompts("deepseek")[0]
        self.assertIn("into Danish, completely and faithfully", prompt)
        self.assertIn("TRANSLATE IT, DO NOT ECHO IT", prompt)
        self.assertIn("## Heading", prompt)

    def test_an_untranslated_reply_falls_back_to_haiku_after_one_retry(self):
        fake = FakeProviders(
            deepseek=f"TITLE: {TITLE}\nCONTENT:\n{ENGLISH_BODY}",
            haiku=f"TITLE: {DANISH_TITLE}\nCONTENT:\n{DANISH_BODY}",
        )
        result = self._translate(fake)

        self.assertEqual(len(fake.prompts("deepseek")), 2)
        self.assertEqual(result["content"], DANISH_BODY)

    def test_none_when_nothing_translates(self):
        self.assertIsNone(self._translate(FakeProviders(deepseek=Exception("down"), haiku=None)))

    def test_the_translation_is_simplified_in_the_target_language(self):
        service = self._service()
        translation = {"title": DANISH_TITLE, "content": DANISH_BODY}
        with patch.object(service, "translate", return_value=translation) as translate, patch.object(
            service, "simplify_text", return_value={"title": "A1"}
        ) as simplify:
            result = service.translate_and_adapt(TITLE, ENGLISH_BODY, "en", "da", "A1")

        self.assertEqual(result, {"title": "A1"})
        translate.assert_called_once_with(TITLE, ENGLISH_BODY, "en", "da")
        simplify.assert_called_once_with(DANISH_TITLE, DANISH_BODY, "A1", "da")

    def test_no_simplification_without_a_translation(self):
        service = self._service()
        with patch.object(service, "translate", return_value=None), patch.object(
            service, "simplify_text"
        ) as simplify:
            self.assertIsNone(service.translate_and_adapt(TITLE, ENGLISH_BODY, "en", "da", "A1"))
        simplify.assert_not_called()


class ParseTranslationReplyTest(TestCase):
    def test_with_and_without_the_content_label(self):
        from zeeguu.core.llm_services.simplification_service import parse_translation_reply

        expected = {"title": "Titel", "content": "## Overskrift\n\nTekst."}
        self.assertEqual(parse_translation_reply("TITLE: Titel\nCONTENT:\n## Overskrift\n\nTekst."), expected)
        self.assertEqual(parse_translation_reply("TITLE: Titel\n\n## Overskrift\n\nTekst."), expected)

    def test_a_sentence_before_the_title_is_not_the_title(self):
        from zeeguu.core.llm_services.simplification_service import parse_translation_reply

        reply = "Here is the translation:\nTITLE: Titel\nCONTENT:\nTekst."
        self.assertEqual(parse_translation_reply(reply), {"title": "Titel", "content": "Tekst."})

    def test_a_reply_without_content_is_an_error(self):
        from zeeguu.core.llm_services.simplification_service import parse_translation_reply

        with self.assertRaises(Exception):
            parse_translation_reply("TITLE: Titel")


class DeeplArticleTest(TestCase):
    def test_deepl_gets_the_blocks_as_html_and_the_markdown_comes_back(self):
        from types import SimpleNamespace

        from zeeguu.core.translation_services import deepl_translate

        calls = []

        def translate_text(texts, **kwargs):
            calls.append((texts, kwargs))
            return [
                SimpleNamespace(text="<h2>Heading</h2><p>- I am afraid.</p><p>5. May, foo_bar</p>"),
                SimpleNamespace(text="Fish &amp; chips"),
            ]

        client = SimpleNamespace(translate_text=translate_text)
        markdown = "## Overskrift\n\n\\- Jeg er bange.\n\n5. maj, foo_bar"
        with patch.object(deepl_translate, "_get_client", return_value=client):
            result = deepl_translate.deepl_translate_article("Fisk & chips", markdown, "en")

        self.assertEqual(
            result, {"title": "Fish & chips", "content": "## Heading\n\n\\- I am afraid.\n\n5\\. May, foo_bar"}
        )
        (html, title), kwargs = calls[0]
        # no list starting at 5, no emphasis in foo_bar: only the markers become tags
        self.assertEqual(html, "<h2>Overskrift</h2><p>- Jeg er bange.</p><p>5. maj, foo_bar</p>")
        self.assertEqual(title, "Fisk &amp; chips")
        self.assertEqual(kwargs, {"target_lang": "EN-US", "tag_handling": "html"})

    def test_a_failing_deepl_is_none(self):
        from types import SimpleNamespace

        from zeeguu.core.translation_services import deepl_translate

        def translate_text(texts, **kwargs):
            raise Exception("Quota for this billing period has been exceeded")

        with patch.object(deepl_translate, "_get_client", return_value=SimpleNamespace(translate_text=translate_text)):
            self.assertIsNone(deepl_translate.deepl_translate_article("Titel", "Tekst.", "en"))


class GoogleArticleTest(TestCase):
    def _post(self, calls, drop=0):
        from types import SimpleNamespace

        def post(url, headers, data, timeout):
            calls.append({"url": url, "headers": headers, **data})
            translated = [{"translatedText": q.replace("Overskrift", "Heading").replace("Fisk", "Fish")} for q in data["q"]]
            body = {"data": {"translations": translated[: len(translated) - drop]}}
            return SimpleNamespace(ok=True, status_code=200, text="", json=lambda: body)

        return post

    def _run(self, calls, title, markdown, source="da", target="en", drop=0):
        from zeeguu.core.translation_services import google_article_translate as g

        with patch.object(g, "_api_key", return_value="SECRET"), patch.object(g.requests, "post", self._post(calls, drop)):
            return g.google_translate_article(title, markdown, source, target)

    def test_the_blocks_go_as_html_and_the_markdown_comes_back(self):
        calls = []
        result = self._run(calls, "Fisk & chips", "## Overskrift\n\n5. maj, foo_bar")

        self.assertEqual(result, {"title": "Fish & chips", "content": "## Heading\n\n5\\. maj, foo_bar"})
        self.assertEqual(calls[0]["q"], ["Fisk &amp; chips", "<h2>Overskrift</h2>", "<p>5. maj, foo_bar</p>"])
        self.assertEqual((calls[0]["source"], calls[0]["target"], calls[0]["format"]), ("da", "en", "html"))

    def test_the_key_goes_in_a_header_not_the_url(self):
        calls = []
        self._run(calls, "Titel", "Tekst.")

        self.assertEqual(calls[0]["headers"], {"X-Goog-Api-Key": "SECRET"})
        self.assertNotIn("SECRET", calls[0]["url"])

    def test_our_indonesian_code_becomes_googles(self):
        calls = []
        self._run(calls, "Judul", "Teks.", source="ind", target="en")

        self.assertEqual(calls[0]["source"], "id")

    def test_a_long_article_goes_in_several_requests_in_order(self):
        from zeeguu.core.translation_services import google_article_translate as g

        calls = []
        paragraphs = [f"Afsnit {i} " + "x" * 1000 for i in range(12)]
        result = self._run(calls, "Titel", "\n\n".join(paragraphs))

        self.assertGreater(len(calls), 1)
        self.assertTrue(all(sum(map(len, c["q"])) <= g.MAX_CHARS_PER_REQUEST for c in calls))
        self.assertEqual(result["content"], "\n\n".join(paragraphs))

    def test_a_paragraph_longer_than_a_request_is_cut_at_sentences_and_put_back(self):
        from zeeguu.core.translation_services import google_article_translate as g

        calls = []
        paragraph = " ".join(f"Sætning nummer {i} handler om fisk." for i in range(400))
        result = self._run(calls, "Titel", f"## Overskrift\n\n{paragraph}")

        sent = [q for c in calls for q in c["q"]]
        self.assertTrue(all(len(q) <= g.MAX_CHARS_PER_REQUEST for q in sent))
        self.assertTrue(all(q.endswith("fisk.") for q in sent[2:]))
        self.assertEqual(result["content"], f"## Heading\n\n{paragraph}")

    def test_fewer_translations_than_segments_is_none(self):
        self.assertIsNone(self._run([], "Titel", "Et.\n\nTo.", drop=1))

    def test_a_failing_google_is_none(self):
        from types import SimpleNamespace
        from zeeguu.core.translation_services import google_article_translate as g

        def post(*args, **kwargs):
            return SimpleNamespace(ok=False, status_code=403, text="quota")

        with patch.object(g, "_api_key", return_value="key"), patch.object(g.requests, "post", post):
            self.assertIsNone(g.google_translate_article("Titel", "Tekst.", "da", "en"))

    def test_no_key_is_none(self):
        from zeeguu.core.translation_services import google_article_translate as g

        with patch.object(g, "_api_key", return_value=None):
            self.assertIsNone(g.google_translate_article("Titel", "Tekst.", "da", "en"))


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

    def test_markdown_headings_are_paragraphs_that_stay_headings(self):
        prompt = get_level_simplification_prompt("da", "Titel", "## Overskrift\n\nTekst.", "A2")

        self.assertIn("Output exactly 2 paragraphs", prompt)
        self.assertIn("[1] ## Overskrift", prompt)
        self.assertIn("is a heading: write its A2 version as a heading", prompt)

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

    def test_partly_glued_text_gets_the_htmls_paragraphs(self):
        from zeeguu.core.llm_services.prompts.level_simplification import text_with_paragraphs

        html = "".join(f"<p>Afsnit nummer {i} handler om noget helt bestemt i dag.</p>" for i in range(8))
        text = (
            "Afsnit nummer 0 handler om noget helt bestemt i dag.\n\n"
            + "".join(f"Afsnit nummer {i} handler om noget helt bestemt i dag." for i in range(1, 8))
        )
        self.assertEqual(len(paragraphs(text_with_paragraphs(text, html))), 8)

    def test_text_that_only_has_fewer_paragraphs_is_kept(self):
        # crawled articles: cleaned text, and HTML with extra bits (affiliate notes, captions)
        from zeeguu.core.llm_services.prompts.level_simplification import text_with_paragraphs

        text = "Saugroboter scheitern oft an Schwellen.\n\nDieser hier nicht, sagt der Test."
        html = (
            "<p>Saugroboter scheitern oft an Schwellen.</p><p>Wenn du über diese Links einkaufst, erhalten wir eine Provision.</p>"
            "<p>Dieser hier nicht, sagt der Test.</p><figcaption>Foto</figcaption>"
        )
        self.assertEqual(text_with_paragraphs(text, html), text)

    def test_no_text_is_lost_from_the_html(self):
        # text directly in a <div>, or in a quote without a <p>, is a paragraph too
        from zeeguu.core.llm_services.prompts.level_simplification import html_paragraphs

        html = "<div>Indledning uden afsnit.<blockquote>Et citat.</blockquote><p>Et <b>rigtigt</b> afsnit.</p>Til sidst.</div>"
        self.assertEqual(html_paragraphs(html), ["Indledning uden afsnit.", "Et citat.", "Et rigtigt afsnit.", "Til sidst."])


class SimplifyCallSitesTest(TestCase):
    """Both Simplify paths hand the model the paragraphs, not the glued text."""

    GLUED = TextWithParagraphsTest.GLUED
    HTML = TextWithParagraphsTest.HTML

    @staticmethod
    def _upload(**fields):
        from types import SimpleNamespace

        from zeeguu.core.model.article_upload import ArticleUpload

        upload = SimpleNamespace(id=1, title="Titel", language=SimpleNamespace(code="da"), **fields)
        upload.markdown_from_html = lambda: ArticleUpload.markdown_from_html(upload)
        upload.markdown = lambda: ArticleUpload.markdown(upload)
        return upload

    def _content_sent(self, call):
        from zeeguu.core.llm_services import simplification_and_classification as sac

        with patch.object(sac, "_create_targeted_simplified_version", return_value=None) as targeted:
            call(sac)
        return targeted.call_args.args[0]

    def test_upload(self):
        upload = self._upload(text_content=self.GLUED, raw_html=self.HTML)
        content = self._content_sent(lambda sac: sac.create_simplified_version_from_upload(None, upload, "A2"))
        self.assertEqual(len(paragraphs(content)), 4)

    def test_upload_keeps_its_headings(self):
        upload = self._upload(text_content="OverskriftTekst.", raw_html="<h2>Overskrift</h2><p>Tekst.</p>")
        content = self._content_sent(lambda sac: sac.create_simplified_version_from_upload(None, upload, "A2"))
        self.assertEqual(content, "## Overskrift\n\nTekst.")

    def test_upload_whose_html_lost_text_sends_its_text(self):
        text = "Første afsnit med mange ord i sig.\n\nAndet afsnit med endnu flere ord i sig her."
        upload = self._upload(text_content=text, raw_html="<p>Første afsnit med mange ord i sig.</p>")
        content = self._content_sent(lambda sac: sac.create_simplified_version_from_upload(None, upload, "A2"))
        self.assertEqual(content, text)

    def test_upload_without_html_sends_its_text(self):
        upload = self._upload(text_content="Første.\n\nAnden.", raw_html=None)
        content = self._content_sent(lambda sac: sac.create_simplified_version_from_upload(None, upload, "A2"))
        self.assertEqual(content, "Første.\n\nAnden.")

    def test_upload_translated_keeps_its_headings(self):
        from types import SimpleNamespace

        from zeeguu.core.llm_services import simplification_and_classification as sac
        from zeeguu.core.llm_services.simplification_service import SimplificationService

        upload = self._upload(text_content="OverskriftTekst.", raw_html="<h2>Overskrift</h2><p>Tekst.</p>")
        upload.url = SimpleNamespace(as_string=lambda: "https://dr.dk/a")
        with patch.object(sac.Article, "find", return_value=None), patch.object(
            SimplificationService, "translate_and_adapt", return_value=None
        ) as translate:
            sac.create_recipient_derivative(None, upload, "en", "A2")
        self.assertEqual(translate.call_args.kwargs["content"], "## Overskrift\n\nTekst.")

    def test_article(self):
        from types import SimpleNamespace

        article = SimpleNamespace(
            id=1, content=self.GLUED, htmlContent=self.HTML, title="Titel", cefr_level="B2",
            language=SimpleNamespace(code="da"), get_fk_difficulty=lambda: 50,
        )
        content = self._content_sent(lambda sac: sac.create_user_specific_simplified_version(None, article, "A2"))
        self.assertEqual(len(paragraphs(content)), 4)
