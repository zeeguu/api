"""
Re-tokenize everything cached in one language, after a change to tokenization
itself: an MWE rule, a lexicon entry, a parser upgrade. Nothing else
invalidates cached tokens, and a text tokenized before the change keeps its
old grouping.

Four caches hold tokens:
  articles             dropped; rebuilt on next read
  pasted texts         cleared; rebuilt on next read (a handful)
  bookmark contexts    re-tokenized here: rebuilt on read, an exercise
    (exercise sentences) session would make one Stanza call per word
  level-adapted        re-tokenized here: nothing rebuilds them, and a row
    summaries/titles   without tokens is not shown
A text that fails to re-tokenize keeps its old tokens.

Run through tools/cleanup_tokenization_cache.py --language CODE, in the
run_task container: it talks to stanza_crawl, so the tens of thousands of
calls made here stay off the Stanza service live readers wait on. Articles
and pasted texts still rebuild on that service, as each is next read.
"""

from sqlalchemy import select

from zeeguu.core.model.article import Article
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText
from zeeguu.core.model.short_text import ShortText
from zeeguu.core.model.source import Source


def _short_texts(language):
    return ShortText.query.filter(
        ShortText.source_id.in_(select(Source.id).where(Source.language_id == language.id)),
        ShortText.tokenized_paragraphs.isnot(None),
    )


def _bookmark_contexts(language):
    return BookmarkContext.query.filter(
        BookmarkContext.language_id == language.id,
        BookmarkContext.cached_tokenized.isnot(None),
    )


def _level_adapted(language):
    return LevelAdaptedArticleText.query.filter(
        LevelAdaptedArticleText.article_id.in_(
            select(Article.id).where(Article.language_id == language.id)
        )
    )


def count_cached(session, language):
    return {
        "articles": ArticleTokenizationCache.count_for_language(session, language.code),
        "pasted texts": _short_texts(language).count(),
        "bookmark contexts": _bookmark_contexts(language).count(),
        "level-adapted texts": _level_adapted(language).count(),
    }


def clear_rebuildable(session, language):
    """Drop the tokens that are rebuilt on next read: articles, pasted texts."""
    ArticleTokenizationCache.delete_for_language(session, language.code)
    _short_texts(language).update(
        {ShortText.tokenized_paragraphs: None}, synchronize_session=False
    )
    session.commit()


# A Stanza service that hangs instead of refusing makes every call wait out
# its 30s timeout: tens of thousands of rows would take days. Stop instead.
MAX_FAILURES_IN_A_ROW = 10
BATCH = 50


class StanzaGaveUp(Exception):
    pass


def _retokenize_rows(session, query, retokenize_row, what, progress):
    """retokenize_row(row) sets the new tokens, or raises and the row keeps
    its old ones. Each row is committed on its own: a run takes hours, and a
    failure (Stanza, a lock wait) must cost one row, not a batch or the rest
    of the run. Rows are loaded BATCH at a time, by id: tens of thousands of
    rows with their token columns would not fit in memory at once.
    Returns (re-tokenized, kept old)."""
    model = query.column_descriptions[0]["entity"]
    ids = [id for (id,) in query.with_entities(model.id).order_by(model.id)]
    done = failed = in_a_row = 0
    for start in range(0, len(ids), BATCH):
        rows = model.query.filter(model.id.in_(ids[start:start + BATCH])).order_by(model.id).all()
        for row in rows:
            row_id = row.id
            try:
                retokenize_row(row)
                session.commit()
                done += 1
                in_a_row = 0
            except Exception as e:
                session.rollback()
                failed += 1
                in_a_row += 1
                progress(f"  {what} {row_id}: kept old tokens ({e})")
                if in_a_row >= MAX_FAILURES_IN_A_ROW:
                    raise StanzaGaveUp(
                        f"{in_a_row} {what} failed in a row; stopped at id {row_id} "
                        f"after {done} re-tokenized. Is the Stanza service up?"
                    )
        # Only these rows: expunge_all would also detach the caller's Language,
        # which every commit has expired.
        for row in rows:
            if row in session:
                session.expunge(row)
        progress(f"  {min(start + BATCH, len(ids))}/{len(ids)} {what}")
    return done, failed


def retokenize_bookmark_contexts(session, language, progress=print):
    """Re-tokenize the cached exercise sentences in place."""
    from zeeguu.core.mwe import tokenize_for_reading

    def retokenize(context):
        if not context.text:
            raise ValueError("its text was deleted")
        context.cached_tokenized = tokenize_for_reading(
            context.get_content(),
            context.language,
            mode="stanza",
            start_token_i=context.token_i,
            start_sentence_i=context.sentence_i,
        )

    return _retokenize_rows(session, _bookmark_contexts(language), retokenize, "bookmark contexts", progress)


def retokenize_level_adapted(session, language, progress=print):
    """Re-tokenize level-adapted summaries and titles in place: without tokens
    a row is not shown at all."""
    from zeeguu.core.mwe import tokenize_for_reading

    def retokenize(row):
        summary = tokenize_for_reading(row.summary, language, mode="stanza") if row.summary else None
        title = tokenize_for_reading(row.title, language, mode="stanza") if row.title else None
        if summary:
            row.tokenized_summary = summary
        if title:
            row.tokenized_title = title

    return _retokenize_rows(session, _level_adapted(language), retokenize, "level-adapted texts", progress)
