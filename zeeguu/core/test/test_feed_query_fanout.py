"""article_infos must not issue queries proportional to the article count.

The feed renders ~15 articles per page. Before this, each one cost roughly ten
round trips: a PersonalCopy query during version selection, the UserArticle /
ArticleDifficultyFeedback / ArticleTopicUserFeedback finds, and the lazy
relationships article_info reads (uploader, url, img_url, feed, cefr_assessment,
topics -- plus topic.topic.title, a second hop).

The guard here is the *shape* of the growth, not an absolute number: more
articles must not mean more queries. An absolute budget would be brittle
against unrelated model changes, while the N+1 it replaces is exactly a
proportional-growth bug.
"""
import json
from unittest import TestCase

from sqlalchemy import event

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

import zeeguu.core
from zeeguu.core.model import Article
from zeeguu.core.model.article_summary_context import ArticleSummaryContext
from zeeguu.core.model.level_adapted_article_title_context import (
    LevelAdaptedArticleTitleContext,
)
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.user_language import UserLanguage

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
        # A learner with a level, reading C1 articles in their language, so the
        # per-level title/summary path runs -- the one real learners hit, and
        # the one a level-less test user silently skips.
        ul = UserLanguage.find_or_create(session, self.user, self.user.learned_language)
        ul.cefr_level = 4  # B2
        session.add(ul)

        tokens = [[[{"text": "hej", "sentence_i": 0, "token_i": 0}]]]
        self.articles = []
        for i in range(8):
            article = ArticleRule().article
            article.language = self.user.learned_language
            article.cefr_level = "C1"
            session.add(article)
            session.flush()
            # Half get a B1 level row, half fall back to their own cached tokens.
            if i % 2:
                LevelAdaptedArticleText.find_or_create(
                    session, article, cefr_level="B1", summary="s",
                    tokenized_summary=tokens, title="t", tokenized_title=tokens,
                )
            else:
                cache = ArticleTokenizationCache.find_or_create(session, article)
                cache.tokenized_title = json.dumps(tokens)
                cache.tokenized_summary = json.dumps(tokens)
                session.add(cache)
            self.articles.append(article)
        session.commit()

    def _queries_for(self, articles):
        # Start from a cold identity map, so a previous call cannot hide a query
        # the next one would otherwise make -- then reload the articles outside
        # the counter, as the feed's search-hit hydration hands them over fresh.
        session.expire_all()
        ids = [a.id for a in articles]
        fresh = Article.query.filter(Article.id.in_(ids)).all()
        fresh.sort(key=lambda a: ids.index(a.id))
        with QueryCounter() as counter:
            UserArticle.article_infos(self.user, fresh, select_appropriate=True)
        return counter.count

    def test_query_count_does_not_grow_with_article_count(self):
        """Every lookup is one query for the whole page, so 8 articles cost what
        2 do.

        Measured on this path: before batching, going 2 -> 8 articles went 52 ->
        176 queries, about 21 per extra article. After, both are ~32.

        A little slack for fixture noise; anything moving back inside the
        per-article loop costs at least one query per article, i.e. +6 here.
        """
        few = self._queries_for(self.articles[:2])
        many = self._queries_for(self.articles)

        assert many - few <= 2, (
            f"{few} queries for 2 articles, {many} for 8. Should be flat; "
            f"something is querying once per article again."
        )

    def test_past_bookmarks_land_on_their_own_article(self):
        """The batched bookmark lookups are keyed by id; check they are handed
        back to the article (or level row) they belong to, and no other."""
        own_summary_article = self.articles[0]  # even: served its own summary
        level_article = self.articles[1]  # odd: served its B1 level row
        level_row = LevelAdaptedArticleText.query.filter_by(
            article_id=level_article.id
        ).one()

        in_summary = BookmarkRule(self.user).bookmark
        ArticleSummaryContext.find_or_create(session, in_summary, own_summary_article)
        in_level_title = BookmarkRule(self.user).bookmark
        LevelAdaptedArticleTitleContext.find_or_create(
            session, in_level_title, level_row
        )
        session.commit()

        infos = {
            i["id"]: i
            for i in UserArticle.article_infos(
                self.user, self.articles, select_appropriate=True
            )
        }

        def ids(payload):
            return [b["id"] for b in payload["past_bookmarks"]]

        assert ids(infos[own_summary_article.id]["interactiveSummary"]) == [
            in_summary.id
        ]
        assert ids(infos[level_article.id]["interactiveTitle"]) == [in_level_title.id]
        for article in self.articles[2:]:
            assert ids(infos[article.id]["interactiveSummary"]) == []
            assert ids(infos[article.id]["interactiveTitle"]) == []

    def test_infos_are_returned_for_every_article(self):
        infos = UserArticle.article_infos(
            self.user, self.articles, select_appropriate=True
        )
        assert len(infos) == len(self.articles)
        assert all("id" in i for i in infos)
