from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.user_rule import UserRule

db_session = zeeguu.core.model.db.session


class ArticleFragmentsTest(ModelTestMixIn, TestCase):
    """Each block of the article's HTML becomes exactly one reader fragment."""

    def _article(self, html, uploader=None):
        article = ArticleRule().article
        article.uploader = uploader
        ArticleFragment.query.filter_by(article_id=article.id).delete()
        article.htmlContent = html
        article.create_article_fragments(db_session)
        db_session.commit()
        return article

    def _fragments(self, html, uploader=None):
        article = self._article(html, uploader)
        return [
            (f.formatting, f.text.content)
            for f in ArticleFragment.get_all_article_fragments_in_order(article.id)
        ]

    def test_paragraph_inside_list_item_is_not_repeated(self):
        # The shape the teacher editor (TipTap) saves every list item in
        html = "<p>Vessels:</p><ul><li><p>Container ships</p></li><li><p>Tankers</p></li></ul>"
        self.assertEqual(
            [("p", "Vessels:"), ("li", "Container ships"), ("li", "Tankers")],
            self._fragments(html),
        )

    def test_nested_list_items_each_appear_once(self):
        html = "<ul><li><p>Ships</p><ul><li><p>Tankers</p></li></ul></li></ul>"
        self.assertEqual(
            [("li", "Ships"), ("li", "Tankers")],
            self._fragments(html),
        )

    def test_list_item_with_several_blocks_keeps_them_apart(self):
        html = "<ul><li><h3>Container ships</h3><p>Carry boxes.</p><p>Largest class.</p></li></ul>"
        self.assertEqual(
            [("li", "Container ships"), ("p", "Carry boxes."), ("p", "Largest class.")],
            self._fragments(html),
        )

    def test_loose_text_before_blocks_carries_the_bullet(self):
        html = "<ul><li><strong>Tankers</strong><p>Carry oil.</p></li></ul>"
        self.assertEqual(
            [("li", "Tankers"), ("p", "Carry oil.")],
            self._fragments(html),
        )

    def test_plain_list_items_and_quotes_unchanged(self):
        html = "<ol><li>One</li></ol><blockquote><p>Quoted</p></blockquote>"
        self.assertEqual(
            [("li", "One"), ("blockquote", "Quoted")],
            self._fragments(html),
        )

    def test_blank_lines_in_uploaded_text_become_one_break(self):
        # Empty <p>s are how the teacher editor (TipTap) saves blank lines
        html = "<p></p><p>Verse one</p><p></p><p></p><p>Verse two</p><p></p>"
        self.assertEqual(
            [("p", "Verse one"), ("break", ""), ("p", "Verse two")],
            self._fragments(html, uploader=UserRule().user),
        )

    def test_blank_lines_in_crawled_article_are_dropped(self):
        html = "<p>One</p><p></p><p>Two</p>"
        self.assertEqual(
            [("p", "One"), ("p", "Two")],
            self._fragments(html),
        )

    def test_break_fragment_is_not_sent_to_the_tokenizer(self):
        article = self._article("<p>One</p><p></p><p>Two</p>", UserRule().user)

        class EchoTokenizer:
            def tokenize_text(self, text, flatten=False):
                assert text, "empty text sent to the tokenizer"
                return [[[text]]]

        with patch("zeeguu.core.mwe.enrich_tokens_with_mwe"):
            fragments = article._tokenize_fragments(EchoTokenizer())

        self.assertEqual(
            [("p", [[["One"]]]), ("break", []), ("p", [[["Two"]]])],
            [(f["formatting"], f["tokens"]) for f in fragments],
        )
