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

USAGE (inside the api container). Without --apply nothing is written.
    python tools/backfill_evergreen_level_texts.py --language da
    python tools/backfill_evergreen_level_texts.py --language da --apply --limit 20
    python tools/backfill_evergreen_level_texts.py --language da --apply
    python tools/backfill_evergreen_level_texts.py --apply          # every language
"""
import argparse
from collections import Counter

# The app must exist before the model imports below can talk to the database.
from zeeguu.api.app import create_app_for_scripts

app = create_app_for_scripts()
app.app_context().push()

from sqlalchemy import or_

from zeeguu.core.content_retriever.article_downloader import _save_classifications
from zeeguu.core.elastic.indexing import create_or_update_article, get_article_hit_in_es
from zeeguu.core.llm_services.simplification_and_classification import (
    assess_and_summarize,
    save_assessment,
)
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText
from zeeguu.core.util.parallel import process_in_parallel

session = db.session

# The crawler does not assess articles shorter than this, so neither do we.
MIN_WORDS = 100

# How many articles we send to the LLM at the same time.
DEFAULT_WORKERS = 6


# ---------------------------------------------------------------------------
# Step 1: which articles need level titles?
# ---------------------------------------------------------------------------


def find_article_ids_without_level_titles(language):
    """IDs of Evergreen articles that have no level title, newest first."""

    # Every article that already has at least one level title.
    rows = session.query(LevelAdaptedArticleText.article_id).filter(
        LevelAdaptedArticleText.title.isnot(None)
    )
    ids_with_titles = {row.article_id for row in rows}

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
    )
    if language:
        query = query.filter(Article.language_id == language.id)

    all_ids = [row.id for row in query.order_by(Article.id.desc())]
    return [article_id for article_id in all_ids if article_id not in ids_with_titles]


# ---------------------------------------------------------------------------
# Step 2: ask the LLM, several articles at the same time
# ---------------------------------------------------------------------------


def article_for_llm(article):
    """Copy what the LLM needs out of the article into a plain dict.
    Runs on the main thread. None means: skip this article."""
    if article.get_word_count() < MIN_WORDS:
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
    """Save the LLM's answer exactly as the crawler would. Main thread only."""
    article = Article.find_by_id(article_id)

    # Writes cefr_level, article_type, summary and the level titles/summaries.
    classifications = save_assessment(session, article, answer)
    # Writes the DISTURBING flag, if the LLM set it.
    _save_classifications(session, article, classifications)

    # Update the search index, but only if the article is already in it.
    try:
        if get_article_hit_in_es(article.id):
            create_or_update_article(article, session)
    except Exception as e:
        print(f"    (Elasticsearch update failed for {article_id}: {str(e)[:80]})")


def is_rejection(error):
    """True if the LLM refused the article on purpose (paywall, advertorial).
    Those are expected, not failures."""
    message = str(error)
    return message.startswith("PAYWALL") or message.startswith("ADVERTORIAL")


def try_to_save(article, answer, error):
    """Save the LLM's answer if there is one.

    Returns (what to count, what to print). The labels it counts:
      ok        assessed and saved
      titled    ... and got at least one level title
      now_news  ... and is now classed `news`, so it leaves Evergreen
      rejected  the LLM said paywall or advertorial; article left untouched
      failed    LLM error or save error
    """
    if error and is_rejection(error):
        return ["rejected"], f"SKIP ({str(error).split(':')[0]})"
    if error:
        return ["failed"], f"FAIL: {str(error)[:100]}"

    try:
        save_answer(article["id"], answer)
    except Exception as e:
        session.rollback()
        return ["failed"], f"FAIL saving: {str(e)[:100]}"

    labels = ["ok"]
    n_titles = len(answer.get("level_titles") or {})
    if n_titles > 0:
        labels.append("titled")
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

    for done, (article, answer, error) in enumerate(results, start=1):
        labels, message = try_to_save(article, answer, error)
        counts.update(labels)  # +1 for each label
        print(f"  [{done}/{len(ids)}] article {article['id']} -> {message}")

    print(
        f"\n=== DONE: {counts['ok']} assessed ({counts['titled']} got level titles,"
        f" {counts['now_news']} now classed news), {counts['rejected']} rejected"
        f" (paywall/advertorial), {counts['short']} under {MIN_WORDS} words,"
        f" {counts['failed']} failed ==="
    )


def main():
    parser = argparse.ArgumentParser(description="Level titles for Evergreen articles")
    parser.add_argument("--language", help="language code; default: every language")
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

    language = None
    if args.language:
        language = Language.query.filter_by(code=args.language).first()
        if language is None:
            print(f"Unknown language code: {args.language}")
            return

    ids = find_article_ids_without_level_titles(language)
    print(f"\n=== Evergreen level titles: {language.name if language else 'all languages'} ===")
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
