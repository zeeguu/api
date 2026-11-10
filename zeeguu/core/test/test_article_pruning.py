"""Every foreign key to article needs a decision about pruning. One nobody made
is found by the nightly prune instead: the database refuses the delete and the
whole run aborts, as article_upload and shared_article did for 11 nights."""
import zeeguu.core.model  # noqa: F401 (registers every table on the metadata)
from zeeguu.core.article_pruning import PROTECTING_COLUMNS
from zeeguu.core.model.db import db

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
