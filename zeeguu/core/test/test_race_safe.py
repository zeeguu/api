from unittest import mock

import pytest

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query

from zeeguu.core.model.article_summary_context import ArticleSummaryContext
from zeeguu.core.model.db import db
from zeeguu.core.model.race_safe import find_or_create, find_or_create_and_report
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

session = db.session


class RaceSafeFindOrCreateTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.article = ArticleRule().article
        self.bookmark = BookmarkRule(UserRule().user).bookmark
        self.filters = dict(bookmark=self.bookmark, article=self.article)
        session.commit()

    def _make(self):
        return ArticleSummaryContext(self.bookmark, self.article)

    def _count(self):
        return ArticleSummaryContext.query.filter_by(
            bookmark_id=self.bookmark.id, article_id=self.article.id
        ).count()

    def test_creates_the_row_when_missing(self):
        row = find_or_create(session, ArticleSummaryContext, self.filters, self._make)

        assert row.id is not None
        assert self._count() == 1

    def test_returns_the_existing_row_without_making_one(self):
        first = find_or_create(session, ArticleSummaryContext, self.filters, self._make)
        make = mock.Mock()

        again = find_or_create(session, ArticleSummaryContext, self.filters, make)

        assert again is first
        make.assert_not_called()
        assert self._count() == 1

    # These spy on commit rather than roll back and look: under pysqlite the
    # savepoint's RELEASE can itself commit, which MySQL doesn't do.
    def test_does_not_commit_by_default(self):
        with mock.patch.object(session, "commit") as commit:
            find_or_create(session, ArticleSummaryContext, self.filters, self._make)
        commit.assert_not_called()

    def test_commit_flag_commits_only_a_created_row(self):
        with mock.patch.object(session, "commit") as commit:
            find_or_create(
                session, ArticleSummaryContext, self.filters, self._make, commit=True
            )
            commit.assert_called_once()

            find_or_create(
                session, ArticleSummaryContext, self.filters, self._make, commit=True
            )
            commit.assert_called_once()

    def test_losing_the_insert_race_returns_the_winners_row(self):
        # The other request's row is in the table, but this request's lookup
        # misses it (on MySQL: it reads an older REPEATABLE READ snapshot).
        winner = self._make()
        session.add(winner)
        session.commit()
        winner_id = winner.id

        # Pending work of the caller that losing the race must not throw away.
        self.article.title = "changed by the caller"

        real_one_or_none = Query.one_or_none
        lookups = []

        def first_lookup_misses(query):
            lookups.append(query)
            if len(lookups) == 1:
                return None
            return real_one_or_none(query)

        with mock.patch.object(Query, "one_or_none", first_lookup_misses):
            loser = find_or_create(
                session, ArticleSummaryContext, self.filters, self._make
            )
        session.commit()

        assert loser.id == winner_id
        assert self._count() == 1
        session.refresh(self.article)
        assert self.article.title == "changed by the caller"

    def test_report_says_whether_this_call_created_the_row(self):
        created_row, created = find_or_create_and_report(
            session, ArticleSummaryContext, self.filters, self._make
        )
        assert created

        found_row, created = find_or_create_and_report(
            session, ArticleSummaryContext, self.filters, self._make
        )
        assert found_row is created_row
        assert not created

    def test_report_says_not_created_when_losing_the_race(self):
        winner = self._make()
        session.add(winner)
        session.commit()

        real_one_or_none = Query.one_or_none
        lookups = []

        def first_lookup_misses(query):
            lookups.append(query)
            if len(lookups) == 1:
                return None
            return real_one_or_none(query)

        with mock.patch.object(Query, "one_or_none", first_lookup_misses):
            row, created = find_or_create_and_report(
                session, ArticleSummaryContext, self.filters, self._make
            )

        assert row.id == winner.id
        assert not created

    def test_collision_on_another_unique_key_raises_the_integrity_error(self):
        # The row make() builds collides on (bookmark, article), but the
        # filters don't cover that key, so there is no winner to return.
        existing = self._make()
        session.add(existing)
        session.commit()

        self.article.title = "changed by the caller"

        with pytest.raises(IntegrityError):
            find_or_create(
                session, ArticleSummaryContext, dict(id=existing.id + 1000), self._make
            )
        session.commit()

        assert self._count() == 1
        session.refresh(self.article)
        assert self.article.title == "changed by the caller"
