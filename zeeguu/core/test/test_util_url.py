from unittest import TestCase

from zeeguu.core.util.url import remove_tracking_query_params


class RemoveTrackingQueryParamsTest(TestCase):

    # The real-world case that motivated this: bt.dk via Google Discover
    # appends gaa_* signed tokens that overflow the 255-char value column.
    def test_strips_gaa_tokens(self):
        url = (
            "https://www.bt.dk/krimi/rumaenske-tyve-haerger"
            "?gaa_at=eafs&gaa_n=AVngi4j3JkJxoD1&gaa_ts=6a1c8a0c&gaa_sig=c9nTTe9K9P"
        )
        self.assertEqual(
            remove_tracking_query_params(url),
            "https://www.bt.dk/krimi/rumaenske-tyve-haerger",
        )

    def test_strips_utm_and_click_ids_keeps_real_params(self):
        url = "https://x.dk/a?id=42&utm_source=news&fbclid=abc&gclid=z&page=2"
        self.assertEqual(
            remove_tracking_query_params(url),
            "https://x.dk/a?id=42&page=2",
        )

    def test_leaves_clean_url_untouched(self):
        url = "https://x.dk/a?id=42&page=2"
        self.assertEqual(remove_tracking_query_params(url), url)

    def test_leaves_non_url_and_empty_untouched(self):
        self.assertEqual(remove_tracking_query_params("OPEN POPUP"), "OPEN POPUP")
        self.assertEqual(remove_tracking_query_params(""), "")
