#!/usr/bin/env python
"""
Give old Evergreen articles their per-level titles.

THE PROBLEM
    Since 28 Aug 2026 the crawler asks an LLM, for every new article, to write
    a simpler title (and summary) for each CEFR level below the article's own.
    Articles crawled before that date never got these titles.

    The home feed mostly shows recent articles, so nobody noticed. But the
    Evergreen tab shows `general` articles of ANY age, so about half its cards
    show the publisher's original headline instead of one at the learner's level.

WHAT THIS SCRIPT DOES
    1. Finds the Evergreen articles that have no level title yet.
    2. For each one, asks the LLM the same question the crawler asks today.
    3. Saves the answer the same way the crawler does.

    Saving rewrites the article's cefr_level, article_type and summary too.
    So if the LLM now says an article is `news`, it leaves the Evergreen tab.
    That is on purpose: it is what would happen if we crawled it today.
    Likewise, an article the LLM rejects as paywall or advertorial is marked
    broken, as the crawler does, and removed from the search index.

WHERE IT DIFFERS FROM THE CRAWLER (old articles have state new ones don't)
    - The tokenized summary cached for the card is cleared, so it is rebuilt
      from the new summary. The cache never refills a summary it already has.
    - Articles whose level summaries carry learners' bookmarks are skipped:
      rewriting those texts would put old bookmarks over new words.
    - Articles with an article_cefr_assessment row are skipped: the card shows
      that row's level, which this script does not update (59 on 18 Nov 2026).

USAGE (inside the api container). Without --apply nothing is written.
    python tools/backfill_evergreen_level_texts.py --language da
    python tools/backfill_evergreen_level_texts.py --language da --apply --limit 20
    python tools/backfill_evergreen_level_texts.py --language da --apply

    --language is required: without it the candidate query would scan the
    whole article table.
"""
import argparse
from collections import Counter

# The app must exist before the model imports below can talk to the database.
from zeeguu.api.app import create_app_for_scripts

app = create_app_for_scripts()
app.app_context().push()

from sqlalchemy import exists, or_

from zeeguu.core.content_retriever.article_downloader import (
    MIN_WORDS_TO_ASSESS,
    _is_paywall,
    _save_classifications,
)
from zeeguu.core.elastic.indexing import remove_from_index, update_article_if_indexed
from zeeguu.core.llm_services.simplification_and_classification import (
    assess_and_summarize,
    save_assessment,
)
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.article_broken_code_map import LowQualityTypes
from zeeguu.core.model.article_cefr_assessment import ArticleCefrAssessment
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
from zeeguu.core.model.language import Language
from zeeguu.core.model.level_adapted_article_summary_context import (
    LevelAdaptedArticleSummaryContext,
)
from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText
from zeeguu.core.util.parallel import process_in_parallel

session = db.session

# How many articles we send to the LLM at the same time.
DEFAULT_WORKERS = 6


# ---------------------------------------------------------------------------
# Step 1: which articles need level titles?
# ---------------------------------------------------------------------------


def find_article_ids_without_level_titles(language):
    """IDs of Evergreen articles that have no level title, newest first."""

    # "There is a level text with a title for this article." The database
    # checks it per article; `~` in front of it below means NOT.
    has_level_title = exists().where(
        LevelAdaptedArticleText.article_id == Article.id,
        LevelAdaptedArticleText.title.isnot(None),
    )
    # "A learner bookmarked a word in one of this article's level summaries."
    has_bookmarked_level_text = exists().where(
        LevelAdaptedArticleText.article_id == Article.id,
        LevelAdaptedArticleSummaryContext.level_adapted_article_text_id
        == LevelAdaptedArticleText.id,
    )
    has_cefr_assessment = exists().where(
        ArticleCefrAssessment.article_id == Article.id
    )

    # The Evergreen pool: the same filters as content_recommender/evergreen.py.
    query = session.query(Article.id).filter(
        Article.article_type == "general",
        Article.parent_article_id.is_(None),  # originals, not simplified copies
        Article.uploader_id.is_(None),  # crawled, not uploaded by a user
        or_(Article.broken.is_(None), Article.broken == 0),
        or_(Article.deleted.is_(None), Article.deleted == 0),
        or_(Article.video.is_(None), Article.video == 0),
        # An A1 article has no simpler level to write a title for.
        or_(Article.cefr_level.is_(None), Article.cefr_level != "A1"),
        ~has_level_title,
        ~has_bookmarked_level_text,  # see the module docstring
        ~has_cefr_assessment,  # see the module docstring
    )
    # language_id is the first column of the index this query can use.
    query = query.filter(Article.language_id == language.id)

    return [row.id for row in query.order_by(Article.id.desc())]


# ---------------------------------------------------------------------------
# Step 2: ask the LLM, several articles at the same time
# ---------------------------------------------------------------------------


def article_for_llm(article):
    """Copy what the LLM needs out of the article into a plain dict.
    Runs on the main thread. None means: skip this article."""
    if article.get_word_count() < MIN_WORDS_TO_ASSESS:
        return None
    return {
        "id": article.id,
        "title": article.title,
        "content": article.get_content(),
        "language_code": article.language.code,
    }


def ask_llm(article, provider):
    """Ask the LLM about one article (a dict from article_for_llm).
    Runs in a worker thread, so it must not touch the database."""
    return assess_and_summarize(
        article["title"],
        article["content"],
        article["language_code"],
        simplification_provider=provider,
    )


# ---------------------------------------------------------------------------
# Step 3: save the answer
# ---------------------------------------------------------------------------


def save_answer(article_id, answer):
    """Save the LLM's answer as the crawler would. Main thread only.
    Returns how many level titles were stored."""
    article = Article.find_by_id(article_id)

    # Writes cefr_level, article_type, summary and the level titles/summaries.
    classifications = save_assessment(session, article, answer)
    # Writes the DISTURBING flag, if the LLM set it.
    _save_classifications(session, article, classifications)

    # The card shows the cached tokenized summary, and the cache never
    # refills a summary it already has: clear it so the new one is used.
    cache = ArticleTokenizationCache.get_for_article(session, article.id)
    if cache and cache.tokenized_summary:
        cache.tokenized_summary = None
        session.add(cache)
        session.commit()

    try:
        update_article_if_indexed(article, session)
    except Exception as e:
        print(f"    (Elasticsearch update failed for {article_id}: {str(e)[:80]})")

    # Count what was stored, not what the LLM sent: a title whose summary
    # failed the language check is dropped.
    return LevelAdaptedArticleText.query.filter(
        LevelAdaptedArticleText.article_id == article_id,
        LevelAdaptedArticleText.title.isnot(None),
    ).count()


def rejection_code(error):
    """The broken code the crawler uses when the LLM refuses an article
    (see _mark_llm_rejection in article_downloader), or None."""
    if "advertorial" in str(error).lower():
        return LowQualityTypes.ADVERTORIAL_LLM
    if _is_paywall(error):
        return LowQualityTypes.LLM_PAYWALL_PATTERN
    return None


def mark_rejected(article_id, code):
    """Mark the article broken, as the crawler does, and take it out of the
    search index so it is no longer recommended."""
    article = Article.find_by_id(article_id)
    article.set_as_broken(session, code)
    try:
        remove_from_index(article)
    except Exception as e:
        print(f"    (Elasticsearch removal failed for {article_id}: {str(e)[:80]})")


def try_to_save(article, answer, error):
    """Save the LLM's answer if there is one.

    Returns (what to count, what to print). The labels it counts:
      ok        assessed and saved
      titled    ... and at least one level title was stored
      untitled  ... but no level title was stored (it stays a candidate)
      now_news  ... and is now classed `news`, so it leaves Evergreen
      rejected  the LLM said paywall or advertorial; marked broken
      failed    LLM error or save error
    """
    code = rejection_code(error) if error else None
    if code:
        try:
            mark_rejected(article["id"], code)
        except Exception as e:
            session.rollback()
            return ["failed"], f"FAIL marking broken: {str(e)[:100]}"
        return ["rejected"], f"BROKEN ({code})"
    if error:
        return ["failed"], f"FAIL: {str(error)[:100]}"

    try:
        n_titles = save_answer(article["id"], answer)
    except Exception as e:
        session.rollback()
        return ["failed"], f"FAIL saving: {str(e)[:100]}"

    labels = ["ok", "titled" if n_titles > 0 else "untitled"]
    if answer.get("article_type") == "news":
        labels.append("now_news")
    level = answer["original_cefr_level"]
    return labels, f"OK {level} {answer.get('article_type')} titles={n_titles}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def print_dry_run(ids):
    print("\n[dry run] nothing written. Newest candidates:")
    newest = Article.query.filter(Article.id.in_(ids[:15])).order_by(Article.id.desc())
    for article in newest:
        level = article.cefr_level or "--"
        title = (article.title or "")[:70]
        print(f"  [{article.id}] {article.language.code} {level}  {title}")
    print("\nRe-run with --apply to write.")


def run_backfill(ids, workers, provider):
    counts = Counter()  # a dict that starts every key at 0

    # Like article_for_llm, but also counts the articles that are too short.
    def prepare(article):
        data = article_for_llm(article)
        if data is None:
            counts["short"] += 1
        return data

    results = process_in_parallel(
        Article,
        ids,
        prepare=prepare,
        work=lambda article: ask_llm(article, provider),
        workers=workers,
    )

    for article, answer, error in results:
        labels, message = try_to_save(article, answer, error)
        counts.update(labels)  # +1 for each label
        # Short articles are skipped before they get here; count them as done.
        done = counts["ok"] + counts["rejected"] + counts["failed"] + counts["short"]
        print(f"  [{done}/{len(ids)}] article {article['id']} -> {message}")

    print(
        f"\n=== DONE: {counts['ok']} assessed ({counts['titled']} got level titles,"
        f" {counts['untitled']} got none, {counts['now_news']} now classed news),"
        f" {counts['rejected']} marked broken (paywall/advertorial),"
        f" {counts['short']} under {MIN_WORDS_TO_ASSESS} words, {counts['failed']} failed ==="
    )


def main():
    parser = argparse.ArgumentParser(description="Level titles for Evergreen articles")
    parser.add_argument("--language", required=True, help="language code, e.g. da")
    parser.add_argument("--apply", action="store_true", help="write (else dry run)")
    parser.add_argument("--limit", type=int, default=0, help="max articles (0 = all)")
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_WORKERS, help="parallel LLM calls"
    )
    parser.add_argument(
        "--provider",
        help="LLM to ask first (deepseek, anthropic); default: the usual order",
    )
    args = parser.parse_args()

    language = Language.query.filter_by(code=args.language).first()
    if language is None:
        print(f"Unknown language code: {args.language}")
        return

    ids = find_article_ids_without_level_titles(language)
    print(f"\n=== Evergreen level titles: {language.name} ===")
    print(f"general originals without a level title: {len(ids)}")

    if args.limit:
        ids = ids[: args.limit]
        print(f"limited to: {len(ids)}")

    if args.apply:
        run_backfill(ids, args.workers, args.provider)
    else:
        print_dry_run(ids)


if __name__ == "__main__":
    main()
