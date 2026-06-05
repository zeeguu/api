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

    # The cleaning must be surgical: a URL without tracking params has to come
    # back byte-for-byte identical, because the result is used as a DB key
    # (url.path) and reconstructed into URLs we serve back. Re-encoding would
    # corrupt signed values and miss lookups against already-stored rows.

    def test_does_not_re_encode_when_nothing_stripped(self):
        # space stays %20 (not +), valueless param stays valueless
        self.assertEqual(
            remove_tracking_query_params("https://x.dk/a?q=hello%20world&flag"),
            "https://x.dk/a?q=hello%20world&flag",
        )

    def test_does_not_mangle_embedded_articleurl(self):
        # an articleURL= wrapper carries an inner URL with its own ?/&/= — these
        # must survive verbatim so as_canonical_string()/split('articleURL=') work
        url = "https://s.dk/read?articleURL=https://bt.dk/x?foo=1&bar=2"
        self.assertEqual(remove_tracking_query_params(url), url)

    def test_preserves_signed_param_encoding_while_stripping(self):
        # a load-bearing signed value keeps its %2F/%3D even when utm is removed
        self.assertEqual(
            remove_tracking_query_params(
                "https://i.cdn/x.jpg?sig=ab%2Fcd%3D&utm_source=x"
            ),
            "https://i.cdn/x.jpg?sig=ab%2Fcd%3D",
        )

    def test_preserves_fragment(self):
        self.assertEqual(
            remove_tracking_query_params("https://x.dk/a?gaa_sig=Z#frag"),
            "https://x.dk/a#frag",
        )
