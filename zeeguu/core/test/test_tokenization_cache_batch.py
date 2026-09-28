"""ensure_populated_batch is now the only thing that fills the cache.

The read path no longer populates on a miss, so if this silently fails nothing
else warms the cache and every article serves cheap tokens forever. The batch
tool swallows per-chunk exceptions, which is exactly how the first version of
this shipped broken: it grouped jobs in a dict keyed by the Language *instance*,
and Language defines __eq__ without __hash__, so Python sets __hash__ = None and
every article raised TypeError: unhashable type: 'Language'.
"""
from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule

import zeeguu.core
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
from zeeguu.core.model.language import Language

session = zeeguu.core.model.db.session


class TokenizationCacheBatchTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.articles = [ArticleRule().article for _ in range(3)]
        for a in self.articles:
            a.summary = "Dette er et resume."
            session.add(a)
        session.commit()
        for a in self.articles:
            ArticleTokenizationCache.delete_for_article(session, a.id)

    def test_language_cannot_key_a_dict(self):
        """Pins the trap itself, so nobody reintroduces a Language-keyed dict."""
        language = self.articles[0].language
        assert Language.__hash__ is None, (
            "Language became hashable -- the language_id keying in "
            "ensure_populated_batch can be simplified back to instances"
        )
        try:
            {language: 1}
            raise AssertionError("expected Language to be unhashable")
        except TypeError:
            pass

    def test_batch_populates_every_article(self):
        populated, failed = ArticleTokenizationCache.ensure_populated_batch(
            session, self.articles
        )
        session.commit()

        assert failed == 0, f"{failed} fields failed to tokenize"
        # title + summary per article
        assert populated == 2 * len(self.articles), f"only populated {populated}"

        for a in self.articles:
            cache = ArticleTokenizationCache.get_for_article(session, a.id)
            assert cache is not None, f"no cache row for article {a.id}"
            assert cache.tokenized_title, f"no title tokens for article {a.id}"
            assert cache.tokenized_summary, f"no summary tokens for article {a.id}"

    def test_batch_is_idempotent(self):
        ArticleTokenizationCache.ensure_populated_batch(session, self.articles)
        session.commit()

        populated, failed = ArticleTokenizationCache.ensure_populated_batch(
            session, self.articles
        )
        assert (populated, failed) == (0, 0), "re-running should tokenize nothing"

    def test_empty_input_is_safe(self):
        assert ArticleTokenizationCache.ensure_populated_batch(session, []) == (0, 0)
