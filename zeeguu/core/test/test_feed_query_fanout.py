"""article_infos must not issue queries proportional to the article count.

The feed renders ~15 articles per page. Before this, each one cost roughly ten
round trips: a PersonalCopy query during version selection, the UserArticle /
ArticleDifficultyFeedback / ArticleTopicUserFeedback finds, and the lazy
relationships article_info reads (uploader, url, img_url, feed, cefr_assessment,
topics -- plus topic.topic.title, a second hop).

The guard here is the *shape* of the growth, not an absolute number: doubling
the articles must not double the queries. An absolute budget would be brittle
against unrelated model changes, while the N+1 it replaces is exactly a
proportional-growth bug.
"""
from unittest import TestCase

from sqlalchemy import event

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.user_rule import UserRule

import zeeguu.core
from zeeguu.core.model.user_article import UserArticle

session = zeeguu.core.model.db.session


class QueryCounter:
    """Counts statements executed on the session's connection."""

    def __init__(self):
        self.count = 0

    def __enter__(self):
        self.count = 0
        self._bind = session.get_bind()
        event.listen(self._bind, "before_cursor_execute", self._on_execute)
        return self

    def __exit__(self, *exc):
        event.remove(self._bind, "before_cursor_execute", self._on_execute)

    def _on_execute(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1


class FeedQueryFanoutTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.articles = [ArticleRule().article for _ in range(8)]
        session.commit()

    def _queries_for(self, articles):
        # Expire everything first, so the identity map from a previous call
        # cannot hide a query the next one would otherwise make.
        session.expire_all()
        with QueryCounter() as counter:
            UserArticle.article_infos(self.user, articles, select_appropriate=True)
        return counter.count

    def test_marginal_query_cost_per_article_stays_low(self):
        """Each extra article should cost a few queries, not ~20.

        Measured on this path: before batching, going 2 -> 8 articles went 52 ->
        176 queries, about 21 per extra article. After, it is roughly 8.

        What is left is genuinely per-article rather than per-user: the title
        and summary bookmark-context lookups, the personal-copy check, and the
        tokenization-cache row. Batching those is possible but is a larger
        change; the bound here is set to catch a return of the per-user
        lookups (isTeacher, cefr level, feature flags) that dominated before,
        each of which cost several queries per article.
        """
        few = self._queries_for(self.articles[:2])
        many = self._queries_for(self.articles)
        marginal = (many - few) / (len(self.articles) - 2)

        assert marginal < 12, (
            f"{marginal:.1f} queries per extra article ({few} for 2, {many} for 8). "
            f"Was ~21 before batching and ~8 after; something is querying per "
            f"article again -- most likely a per-user lookup back inside the loop."
        )

    def test_infos_are_returned_for_every_article(self):
        infos = UserArticle.article_infos(
            self.user, self.articles, select_appropriate=True
        )
        assert len(infos) == len(self.articles)
        assert all("id" in i for i in infos)
