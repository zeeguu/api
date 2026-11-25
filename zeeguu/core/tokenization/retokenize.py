"""
Re-tokenize everything cached in one language, after a change to tokenization
itself: an MWE rule, a lexicon entry, a parser upgrade. Nothing else
invalidates cached tokens, and a text tokenized before the change keeps its
old grouping.

Four caches hold tokens:
  articles             dropped; rebuilt on next read
  pasted texts         cleared; rebuilt on next read
  bookmark contexts    cleared; rebuilt on next read (the exercise sentences)
  level-adapted        re-tokenized here: nothing rebuilds them, and a row
    summaries/titles   without tokens is not shown

Run through tools/cleanup_tokenization_cache.py --language CODE.
"""

from sqlalchemy import null, select

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
    """Drop the tokens that are rebuilt on next read."""
    ArticleTokenizationCache.delete_for_language(session, language.code)
    # null(), not None: on a JSON column None stores the JSON value null
    _short_texts(language).update(
        {ShortText.tokenized_paragraphs: null()}, synchronize_session=False
    )
    _bookmark_contexts(language).update(
        {BookmarkContext.cached_tokenized: null()}, synchronize_session=False
    )
    session.commit()


def retokenize_level_adapted(session, language, progress=print):
    """Re-tokenize level-adapted summaries and titles in place. A row that fails
    keeps its old tokens: without them it would not be shown at all.
    Returns (re-tokenized, kept old)."""
    from zeeguu.core.mwe import tokenize_for_reading

    def tokenized(text):
        return tokenize_for_reading(text, language, mode="stanza") if text else None

    rows = _level_adapted(language).all()
    failed = 0
    for i, row in enumerate(rows, 1):
        try:
            summary, title = tokenized(row.summary), tokenized(row.title)
        except Exception as e:
            failed += 1
            progress(f"  level-adapted text {row.id}: kept old tokens ({e})")
            continue
        if summary:
            row.tokenized_summary = summary
        if title:
            row.tokenized_title = title
        if i % 50 == 0:
            session.commit()
            progress(f"  {i}/{len(rows)} level-adapted texts")
    session.commit()
    return len(rows) - failed, failed
