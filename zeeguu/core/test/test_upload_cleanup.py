import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.content_cleaning.upload_cleanup import clean_html, cleanup_upload

PAGE = (
    "<div><h2>Slanger</h2><p>Før.</p>"
    "<figure><iframe></iframe><div><h5>Hov! Her ligger et element fra en tjeneste, der bruger cookies.</h5></div>"
    "<figcaption>Se slangen. (Video: Youtube)</figcaption></figure>"
    "<p>Annonce:</p><p>Efter, med <b>fed</b> tekst.</p><div><h2><span>\\</span> Læs også</h2></div></div>"
)


class CleanHtmlTest(TestCase):
    def test_figures_and_dropped_blocks_go(self):
        self.assertEqual(
            clean_html(PAGE, ["Annonce:", "## \\ Læs også"], ["## Slanger", "Før.", "Efter, med fed tekst."]),
            "<div><h2>Slanger</h2><p>Før.</p><p>Efter, med <b>fed</b> tekst.</p></div>",
        )

    def test_a_text_that_is_also_kept_stays(self):
        html = "<p>Læs også</p><p>Læs også</p>"
        self.assertEqual(clean_html(html, ["Læs også"], ["Læs også"]), html)

    def test_a_dropped_block_matches_through_its_escape_and_spacing(self):
        html = "<p>- Jeg er bange.</p><table><tr><td>Navn</td><td>Alder</td></tr></table><p>Tekst.</p>"
        self.assertEqual(clean_html(html, ["\\- Jeg er bange.", "Navn Alder"], ["Tekst."]), "<p>Tekst.</p>")


class CleanupUploadTest(TestCase):
    def test_the_upload_keeps_only_the_story(self):
        session = SimpleNamespace(added=[], add=lambda o: session.added.append(o), commit=lambda: None)
        upload = SimpleNamespace(
            id=7, title="Slanger", language=SimpleNamespace(code="da"), raw_html=PAGE,
            text_content="Slanger Før. Hov! Her ligger et element. Se slangen. Annonce: Efter, med fed tekst. Læs også",
        )
        upload.markdown_from_html = lambda: "## Slanger\n\nFør.\n\nAnnonce:\n\nEfter, med fed tekst.\n\n## \\ Læs også"
        reply = {"drops": [{"block": 2, "reason": "ad", "note": "label"}, {"block": 4, "reason": "related_links", "note": ""}],
                 "mixed_blocks": [], "incomplete": False, "incomplete_note": ""}

        with patch("zeeguu.core.llm_services.deepseek_service.DeepSeekService") as service:
            service.return_value._make_deepseek_request.return_value = json.dumps(reply)
            cleanup_upload(session, upload)

        self.assertEqual(upload.text_content, "SlangerFør.Efter, med fed tekst.")
        cleanup, *blocks = session.added[:-1]
        self.assertEqual(cleanup.original_html, PAGE)
        self.assertEqual([(b.block_i, b.kept, b.reason) for b in blocks],
                         [(0, True, None), (1, True, None), (2, False, "ad"), (3, True, None), (4, False, "related_links")])
