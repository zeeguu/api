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
        html = '<p>Et <b>rigtigt</b> <a href="https://x.dk">link</a><br>videre.<img src="a.jpg"></p><script>x()</script>'
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
