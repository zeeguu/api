#!/usr/bin/env python
"""
Backfill: per-level titles and summaries for the Evergreen tab's articles.

The crawler writes a title per CEFR level only since 28 Aug 2026 (88745d30),
and level summaries only since mid-Aug. The home feed favors recent articles,
so it barely shows anything older. The Evergreen tab ignores dates
(content_recommender/evergreen.py), so about half its cards show the
publisher's own headline instead of one at the learner's level. On 16 Nov
2026, 14k of 35k `general` originals had no level title: da 2096 of 3141,
fr 2926 of 5252, en 2923 of 5794.

For each such article this re-runs the crawler's own assessment
(assess_and_summarize + save_assessment): same prompt, same genie order
(DeepSeek first). That rewrites the article's cefr_level, article_type and
summary as today's crawler would see them, and creates or updates the
LevelAdaptedArticleText row for every level below the original. An article
the LLM now calls `news` leaves the tab, as it would if crawled today. One
the LLM rejects (paywall, advertorial) is left untouched and counted.

The LLM calls run in a thread pool; every database write stays on the main
thread. The DISTURBING classification is saved like the crawler saves it. If
the article is in Elasticsearch, its document is updated; an article not in
the index is not added.

Usage (inside the api container), dry run first:
    python tools/backfill_evergreen_level_texts.py --language da
    python tools/backfill_evergreen_level_texts.py --language da --apply --limit 20
    python tools/backfill_evergreen_level_texts.py --language da --apply
    python tools/backfill_evergreen_level_texts.py --apply          # every language
"""
import argparse
from concurrent.futures import ThreadPoolExecutor

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from sqlalchemy import exists, or_

from zeeguu.core.content_retriever.article_downloader import _save_classifications
from zeeguu.core.llm_services.simplification_and_classification import (
    assess_and_summarize,
    save_assessment,
)
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText

session = db.session

MIN_WORDS = 100  # assess_summarize_and_classify skips shorter ones too


def candidate_ids(language):
    """The Evergreen pool's articles (same filters as _evergreen_articles) that
    have no level title at all, newest first, as the tab ranks its pool."""
    has_level_title = exists().where(
        LevelAdaptedArticleText.article_id == Article.id,
        LevelAdaptedArticleText.title.isnot(None),
    )
    query = db.session.query(Article.id).filter(
        Article.article_type == "general",
        Article.parent_article_id.is_(None),
        Article.uploader_id.is_(None),
        or_(Article.broken.is_(None), Article.broken == 0),
        or_(Article.deleted.is_(None), Article.deleted == 0),
        or_(Article.video.is_(None), Article.video == 0),
        # an A1 original has no simpler level to write a title for
        or_(Article.cefr_level.is_(None), Article.cefr_level != "A1"),
        ~has_level_title,
    )
    if language:
        query = query.filter(Article.language_id == language.id)
    return [row[0] for row in query.order_by(Article.id.desc())]


def assess(job, provider):
    """Runs in a worker thread: the LLM call only, no database."""
    article_id, title, content, language_code = job
    try:
        return article_id, assess_and_summarize(
            title, content, language_code, simplification_provider=provider
        ), None
    except Exception as e:
        return article_id, None, e


def reindex(article):
    from zeeguu.core.elastic.indexing import get_article_hit_in_es
    from zeeguu.core.elastic.indexing import create_or_update_article

    if get_article_hit_in_es(article.id):
        create_or_update_article(article, session)


def main():
    p = argparse.ArgumentParser(description="Level titles for Evergreen articles")
    p.add_argument("--language", help="language code; default: every language")
    p.add_argument("--apply", action="store_true", help="write (else dry run)")
    p.add_argument("--limit", type=int, default=0, help="cap on articles (0 = all)")
    p.add_argument("--workers", type=int, default=6, help="parallel LLM calls")
    p.add_argument(
        "--provider",
        help="genie to ask first (deepseek, anthropic); default: the declared order",
    )
    args = p.parse_args()

    language = None
    if args.language:
        language = Language.query.filter_by(code=args.language).first()
        if not language:
            print(f"Unknown language code: {args.language}")
            return

    ids = candidate_ids(language)
    scope = language.name if language else "all languages"
    print(f"\n=== Evergreen level titles: {scope} ===")
    print(f"general originals without a level title: {len(ids)}")
    if args.limit:
        ids = ids[: args.limit]
        print(f"limited to: {len(ids)}")

    if not args.apply:
        print("\n[dry run] nothing written. Newest candidates:")
        for article in Article.query.filter(Article.id.in_(ids[:15])).order_by(
            Article.id.desc()
        ):
            print(
                f"  [{article.id}] {article.language.code} {article.cefr_level or '--'}"
                f"  {(article.title or '')[:70]}"
            )
        print("\nRe-run with --apply to write.")
        return

    counts = {"ok": 0, "titled": 0, "now_news": 0, "rejected": 0, "short": 0, "failed": 0}
    chunk_size = args.workers * 4
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for start in range(0, len(ids), chunk_size):
            jobs = []
            for article in Article.query.filter(
                Article.id.in_(ids[start : start + chunk_size])
            ):
                if article.get_word_count() < MIN_WORDS:
                    counts["short"] += 1
                    continue
                jobs.append(
                    (article.id, article.title, article.get_content(), article.language.code)
                )
            # Free the chunk's contents before the next one loads.
            session.expunge_all()

            for article_id, result, error in pool.map(
                lambda job: assess(job, args.provider), jobs
            ):
                done += 1
                prefix = f"  [{done}/{len(ids)}] article {article_id}"
                if error:
                    message = str(error)
                    if message.startswith(("PAYWALL", "ADVERTORIAL")):
                        counts["rejected"] += 1
                        print(f"{prefix} -> SKIP ({message.split(':')[0]})")
                    else:
                        counts["failed"] += 1
                        print(f"{prefix} -> FAIL: {message[:100]}")
                    continue
                try:
                    article = Article.find_by_id(article_id)
                    _save_classifications(
                        session, article, save_assessment(session, article, result)
                    )
                    try:
                        reindex(article)
                    except Exception as e:
                        print(f"{prefix}    (ES update failed: {str(e)[:80]})")
                    counts["ok"] += 1
                    n_titles = len(result.get("level_titles") or {})
                    if n_titles:
                        counts["titled"] += 1
                    if result.get("article_type") == "news":
                        counts["now_news"] += 1
                    print(
                        f"{prefix} -> OK {result['original_cefr_level']}"
                        f" {result.get('article_type')} titles={n_titles}"
                    )
                except Exception as e:
                    session.rollback()
                    counts["failed"] += 1
                    print(f"{prefix} -> FAIL saving: {str(e)[:100]}")
            session.expunge_all()

    print(
        f"\n=== DONE: {counts['ok']} assessed ({counts['titled']} got level titles,"
        f" {counts['now_news']} now classed news), {counts['rejected']} rejected"
        f" (paywall/advertorial), {counts['short']} under {MIN_WORDS} words,"
        f" {counts['failed']} failed ==="
    )


if __name__ == "__main__":
    main()
