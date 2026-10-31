from unittest import TestCase

from zeeguu.core.content_cleaning.html_to_markdown import html_to_markdown


class HtmlToMarkdownTest(TestCase):
    def test_headings_lists_and_quotes_keep_their_markers(self):
        html = (
            "<h2>Derfor frygter børn værnepligten</h2><p>Første afsnit.</p>"
            "<ul><li><p>Et punkt.</p></li><li>Et andet.</li></ul>"
            "<ol><li>Først.</li></ol><blockquote>Et citat.</blockquote><h4>Lille</h4>"
        )
        self.assertEqual(
            html_to_markdown(html).split("\n\n"),
            ["## Derfor frygter børn værnepligten", "Første afsnit.", "- Et punkt.", "- Et andet.", "1. Først.", "> Et citat.", "### Lille"],
        )

    def test_a_heading_inside_a_paragraph_is_a_heading(self):
        # DR's markup: <p><h2>…</h2></p>
        self.assertEqual(html_to_markdown("<div><p><h2>Overskrift</h2></p><p>Tekst.</p></div>"), "## Overskrift\n\nTekst.")

    def test_a_dash_that_opens_a_paragraph_does_not_make_a_list(self):
        self.assertEqual(html_to_markdown("<p>- Jeg er bange, siger Agnes.</p>"), "\\- Jeg er bange, siger Agnes.")
        self.assertEqual(html_to_markdown("<p>1. maj er en fridag.</p>"), "1\\. maj er en fridag.")

    def test_inline_markup_becomes_text_and_images_go(self):
        html = '<p>Et <b>rigtigt</b> <a href="https://x.dk">link</a> videre.<img src="a.jpg"></p><script>x()</script>'
        self.assertEqual(html_to_markdown(html), "Et rigtigt link videre.")

    def test_text_directly_in_a_div_is_a_paragraph(self):
        html = "<div>Indledning uden afsnit.<p>Et afsnit.</p>Til sidst.</div>"
        self.assertEqual(html_to_markdown(html).split("\n\n"), ["Indledning uden afsnit.", "Et afsnit.", "Til sidst."])

    def test_escaped_paragraphs_render_as_written(self):
        import markdown2

        markdown = html_to_markdown("<p>- Jeg er bange.</p><p>1. maj er en fridag.</p><p># 3 på listen.</p>")
        self.assertEqual(
            markdown2.markdown(markdown).split(),
            "<p>- Jeg er bange.</p> <p>1. maj er en fridag.</p> <p># 3 på listen.</p>".split(),
        )

    def test_line_breaks_separate_paragraphs(self):
        # dialogue laid out with <br>, as the paragraphs html_paragraphs gave before
        self.assertEqual(html_to_markdown("<p>- Hej<br>- Nej<br/>Ja</p>").split("\n\n"), ["\\- Hej", "\\- Nej", "Ja"])

    def test_a_table_row_is_one_paragraph(self):
        html = "<table><tr><th>Navn</th><th>Alder</th></tr><tr><td>Agnes</td><td>12</td></tr></table>"
        self.assertEqual(html_to_markdown(html).split("\n\n"), ["Navn Alder", "Agnes 12"])

    def test_an_article_inside_a_form_is_kept(self):
        self.assertEqual(html_to_markdown("<form><p>Artiklen.</p><button>Send</button></form>"), "Artiklen.")

    def test_markdown_to_html_reads_only_the_block_markers(self):
        from zeeguu.core.content_cleaning.html_to_markdown import markdown_to_html

        markdown = "## A <b>\n\n\\- Hej.\n\n12\\. maj\n\n5. maj, foo_bar\n\n- punkt\n\n1. først\n\n> citat"
        self.assertEqual(
            markdown_to_html(markdown),
            "<h2>A &lt;b&gt;</h2><p>- Hej.</p><p>12. maj</p><p>5. maj, foo_bar</p>"
            "<ul><li>punkt</li></ul><ol><li>først</li></ol><blockquote>citat</blockquote>",
        )
        self.assertEqual(html_to_markdown(markdown_to_html(markdown)), markdown.replace("5. maj", "5\\. maj"))

    def test_escape_marker_and_its_inverse(self):
        from zeeguu.core.content_cleaning.html_to_markdown import escape_marker, unescape_marker

        cases = {
            "- Jeg er bange.": "\\- Jeg er bange.",
            "## Tre ting.": "\\## Tre ting.",
            "> Et citat.": "\\> Et citat.",
            "12. maj.": "12\\. maj.",
            "3) Tredje.": "3\\) Tredje.",
            "-5 grader.": "-5 grader.",
            "2026 blev varm.": "2026 blev varm.",
            "#hashtag": "#hashtag",
            "Tekst.": "Tekst.",
        }
        for text, escaped in cases.items():
            self.assertEqual(escape_marker(text), escaped)
            self.assertEqual(unescape_marker(escaped), text)
