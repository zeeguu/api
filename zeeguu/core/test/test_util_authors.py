from unittest import TestCase

from zeeguu.core.util.authors import clean_authors


class CleanAuthorsTest(TestCase):

    # All the "input" strings below are verbatim shapes pulled from the prod
    # `article.authors` column, where newspaper/readability parsing captured a
    # publisher's "published on <date>" line as if it were an author. See the
    # two ingestion call sites feeding Article.__init__:
    #   content_retriever/article_downloader.py  (", ".join(np_article.authors))
    #   content_retriever/parse_with_readability_server.py  (byline fallback)

    def test_drops_junk_part_keeps_real_author(self):
        # The dominant case (~30k rows): junk date line as a separate first part.
        self.assertEqual(
            clean_authors("Publiceret D., Søren Rosenberg Pedersen"),
            "Søren Rosenberg Pedersen",
        )

    def test_pure_junk_becomes_empty(self):
        # French illvid/science feeds: the whole byline is a date fragment.
        self.assertEqual(clean_authors("Publié Le Mai À"), "")
        self.assertEqual(clean_authors("Publié Le"), "")
        self.assertEqual(clean_authors("Published by sisselofstad"), "")

    def test_junk_with_embedded_name_and_trailing_noise(self):
        # We deliberately drop the whole part rather than try to recover the
        # name buried after the date + "Link kopieret..." trailer — these are a
        # tiny minority and false-recovery would be worse than showing none.
        self.assertEqual(
            clean_authors(
                "Publiceret d. 14.05.22\n     Af Marie Wium     \n"
                "        Link kopieret til udklipsholderen"
            ),
            "",
        )

    def test_real_authors_untouched(self):
        self.assertEqual(
            clean_authors("Jens Hansen, Marie Wium"), "Jens Hansen, Marie Wium"
        )

    def test_real_name_starting_like_a_publish_verb_is_kept(self):
        # Word-boundary anchoring: "Publius" must not match the "publie" prefix.
        self.assertEqual(clean_authors("Publius Cornelius"), "Publius Cornelius")

    def test_empty_and_none_pass_through(self):
        self.assertEqual(clean_authors(""), "")
        self.assertIsNone(clean_authors(None))
