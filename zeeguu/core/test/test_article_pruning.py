"""Every foreign key to article needs a decision about pruning. One nobody made
is found by the nightly prune instead: the database refuses the delete and the
whole run aborts, as article_upload and shared_article did for 11 nights."""
from unittest import TestCase

import zeeguu.core.model  # noqa: F401 (registers every table on the metadata)
from zeeguu.core.article_pruning import (
    PROTECTING_COLUMNS,
    PROTECTING_VIA_OWNED_ROWS,
    articles_with_contexts_in_owned_rows,
)
from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.model.article_fragment_context import ArticleFragmentContext
from zeeguu.core.model.level_adapted_article_summary_context import LevelAdaptedArticleSummaryContext
from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText
from zeeguu.core.model.level_adapted_article_title_context import LevelAdaptedArticleTitleContext
from zeeguu.core.model.db import db
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule

# Rows that belong to their article and go with it. Each needs ON DELETE CASCADE
# in the database, which many of these models do not declare: listing a table
# here does not make it cascade, a migration does.
CASCADE_OWNED_COLUMNS = {
    ("article", "parent_article_id"),
    ("article_broken_code_map", "article_id"),
    ("article_cefr_assessment", "article_id"),
    ("article_classification", "article_id"),
    ("article_fragment", "article_id"),
    ("article_public_code", "article_id"),
    ("article_tokenization_cache", "article_id"),
    ("article_topic_map", "article_id"),
    ("article_url_keyword_map", "article_id"),
    ("difficulty_lingo_rank", "article_id"),
    ("evergreen_impression", "article_id"),
    ("grammar_correction_log", "article_id"),
    ("level_adapted_article_text", "article_id"),
    ("public_translation", "article_id"),
}


def _columns_pointing_at_article():
    return {
        (table.name, foreign_key.parent.name)
        for table in db.metadata.tables.values()
        for foreign_key in table.foreign_keys
        if foreign_key.target_fullname == "article.id"
    }


def test_every_foreign_key_to_article_has_a_pruning_decision():
    undecided = (
        _columns_pointing_at_article() - set(PROTECTING_COLUMNS) - CASCADE_OWNED_COLUMNS
    )

    assert not undecided, (
        f"{sorted(undecided)} point at article. If their rows keep the article "
        "alive, add the table to PROTECTING_TABLES (a column not named article_id "
        "goes in PROTECTING_COLUMNS); if they go with it, make the "
        "foreign key ON DELETE CASCADE and add them to CASCADE_OWNED_COLUMNS."
    )


def test_no_column_is_both_protecting_and_cascading():
    assert not set(PROTECTING_COLUMNS) & CASCADE_OWNED_COLUMNS



def test_every_foreign_key_into_a_row_the_article_owns_has_a_pruning_decision():
    owned_tables = {table for table, _ in CASCADE_OWNED_COLUMNS if table != "article"}
    into_owned_rows = {
        (table.name, foreign_key.parent.name, foreign_key.column.table.name)
        for table in db.metadata.tables.values()
        for foreign_key in table.foreign_keys
        if foreign_key.column.table.name in owned_tables
    }

    undecided = into_owned_rows - set(PROTECTING_VIA_OWNED_ROWS)

    assert not undecided, (
        f"{sorted(undecided)} point at rows that are deleted with their article. "
        "If their rows keep the article alive, add them to PROTECTING_VIA_OWNED_ROWS."
    )


class ContextsInOwnedRowsKeepTheirArticle(ModelTestMixIn, TestCase):
    """A bookmark context in a level-adapted summary or title, or in a fragment,
    points at a row the article owns, not at the article."""

    def setUp(self):
        super().setUp()
        self.user = UserRule().user

    def _level_adapted_text(self):
        return LevelAdaptedArticleText.find_or_create(
            db.session, ArticleRule().article, cefr_level="A2",
            summary="summary at A2", tokenized_summary=[], title="title at A2",
        )

    def _bookmark(self):
        return BookmarkRule(self.user).bookmark

    def test_a_bookmarked_level_adapted_summary_keeps_its_article(self):
        bookmarked = self._level_adapted_text()
        unbookmarked = self._level_adapted_text()
        db.session.add(LevelAdaptedArticleSummaryContext(self._bookmark(), bookmarked))
        db.session.commit()

        kept = articles_with_contexts_in_owned_rows(db.session)

        assert bookmarked.article_id in kept
        assert unbookmarked.article_id not in kept

    def test_a_bookmarked_level_adapted_title_keeps_its_article(self):
        bookmarked = self._level_adapted_text()
        db.session.add(LevelAdaptedArticleTitleContext(self._bookmark(), bookmarked))
        db.session.commit()

        assert bookmarked.article_id in articles_with_contexts_in_owned_rows(db.session)

    def test_a_bookmarked_fragment_keeps_its_article(self):
        fragment = ArticleFragment.find_or_create(db.session, ArticleRule().article, "Ein Satz.", 0)
        db.session.add(ArticleFragmentContext(self._bookmark(), fragment))
        db.session.commit()

        assert fragment.article_id in articles_with_contexts_in_owned_rows(db.session)
