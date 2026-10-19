"""Oversized tokenizations are not cached.

A 2.4 MB cache write dropped the MySQL connection ("server has gone away")
on prod, so _cache_tokenized_content skips anything over the limit.
"""
from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule

import zeeguu.core
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache

session = zeeguu.core.model.db.session

TOKENIZED = {
    "tokenized_fragments": [{"tokens": ["x" * 100]}],
    "tokenized_title_new": {},
    "tokenized_title": [],
}


class TokenizationCacheSizeLimitTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.article = ArticleRule().article
        session.add(self.article)
        session.commit()
        ArticleTokenizationCache.delete_for_article(session, self.article.id)

    def test_oversized_tokenization_is_not_cached(self):
        with patch("zeeguu.core.model.article.MAX_CACHED_TOKENIZATION_CHARS", 50):
            self.article._cache_tokenized_content(session, TOKENIZED)

        assert ArticleTokenizationCache.get_for_article(session, self.article.id) is None

    def test_normal_tokenization_is_cached(self):
        self.article._cache_tokenized_content(session, TOKENIZED)

        cache = ArticleTokenizationCache.get_for_article(session, self.article.id)
        assert cache is not None and cache.tokenized_content
