"""The feed read path must never call the stanza service.

Tokenizing inline means an HTTP round trip to a service that runs one
single-threaded worker for the whole install; in production it logged 5-8s for
titles of a few dozen characters, and the feed asks for up to 15 in a row. A
cache miss now degrades to cheap NLTK tokens and the backfill tool warms the
real cache out of band.

These tests pin the two halves of that contract: nothing reaches stanza, and a
miss still returns tappable tokens rather than nothing.
"""
from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.user_rule import UserRule

import zeeguu.core
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
from zeeguu.core.model.user_article import UserArticle

session = zeeguu.core.model.db.session


class FeedNeverTokenizesInlineTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.article = ArticleRule().article
        self.article.summary = "Dette er et resume."
        session.add(self.article)
        session.commit()
        # The case under test: no cache row at all for this article.
        ArticleTokenizationCache.delete_for_article(session, self.article.id)

    def test_article_infos_does_not_populate_the_cache(self):
        with patch.object(
            ArticleTokenizationCache, "ensure_populated"
        ) as ensure_populated:
            UserArticle.article_infos(
                self.user, [self.article], select_appropriate=False
            )
        ensure_populated.assert_not_called()

    def test_summary_info_does_not_populate_the_cache(self):
        with patch.object(
            ArticleTokenizationCache, "ensure_populated"
        ) as ensure_populated:
            UserArticle.user_article_summary_info(self.user, self.article)
        ensure_populated.assert_not_called()

    def test_a_miss_still_returns_tappable_title_tokens(self):
        result = UserArticle.user_article_summary_info(self.user, self.article)

        assert "tokenized_title" in result, "a cache miss must still yield a title"
        tokens = result["tokenized_title"]["tokens"]
        assert tokens, "title tokens must not be empty on a cache miss"
        # paragraphs -> sentences -> tokens, the shape the client renders
        assert isinstance(tokens[0], list)
        assert isinstance(tokens[0][0], list)

    def test_a_miss_still_returns_summary_tokens(self):
        result = UserArticle.user_article_summary_info(self.user, self.article)

        assert "tokenized_summary" in result
        assert result["tokenized_summary"]["tokens"]

    def test_cheap_tokens_is_none_for_empty_text(self):
        assert (
            ArticleTokenizationCache.cheap_tokens("", self.article.language) is None
        )
        assert (
            ArticleTokenizationCache.cheap_tokens(None, self.article.language) is None
        )
