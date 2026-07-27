#!/usr/bin/env python
"""
Backfill tokenization cache for simplified articles.

The recommended feed renders each simplified article's title/summary as tappable
preview cards, which requires MWE tokenization. That work is now done at crawl
time for the simplified children too (see article_downloader), but only for
articles crawled after that shipped. This tool warms the cache for the existing
backlog so no one pays the tokenization cost inline on the feed request path.

Scope is capped at the cache's own retention window: cleanup_tokenization_cache
deletes rows older than 7 days, so warming articles older than that would just be
thrown away. Default --days matches that (7). Anything older re-warms cheaply
on-demand (~130ms) the first time it's shown.

Safe to re-run: only tokenizes articles still missing a title in the cache, and
the cache is regenerable (see cleanup_tokenization_cache.py).

Usage:
    python -m tools.backfill_tokenization_cache [--days N] [--language da] [--limit N] [--dry-run]
"""
import argparse
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache

app = create_app_for_scripts()
app.app_context().push()

COMMIT_EVERY = 50


def articles_needing_cache(days, language_code, limit):
    """Simplified articles from the last `days` whose title tokens aren't cached yet."""
    cutoff = datetime.now() - timedelta(days=days)
    q = (
        db.session.query(Article)
        .outerjoin(
            ArticleTokenizationCache,
            ArticleTokenizationCache.article_id == Article.id,
        )
        .filter(Article.parent_article_id.isnot(None))
        .filter(Article.published_time > cutoff)
        .filter((Article.broken == 0) | (Article.broken.is_(None)))
        .filter((Article.deleted == 0) | (Article.deleted.is_(None)))
        # missing cache row entirely, or row exists but title never tokenized
        .filter(
            (ArticleTokenizationCache.article_id.is_(None))
            | (ArticleTokenizationCache.tokenized_title.is_(None))
        )
        .order_by(Article.published_time.desc())
    )
    if language_code:
        lang = Language.find(language_code)
        q = q.filter(Article.language_id == lang.id)
    if limit:
        q = q.limit(limit)
    return q.all()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill tokenization cache for simplified articles"
    )
    parser.add_argument("--days", type=int, default=7, help="Only articles published within the last N days (default: 7, matching cache retention)")
    parser.add_argument("--language", type=str, default=None, help="Restrict to a language code (e.g. da). Default: all.")
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of articles processed.")
    parser.add_argument("--dry-run", action="store_true", help="Only report how many articles would be warmed.")
    args = parser.parse_args()

    articles = articles_needing_cache(args.days, args.language, args.limit)
    scope = f"last {args.days} days" + (f", language={args.language}" if args.language else "")
    print(f"Found {len(articles)} simplified articles needing tokenization cache ({scope}).")

    if args.dry_run:
        print("Dry run - nothing written.")
        return

    warmed = 0
    failed = 0
    for i, article in enumerate(articles, 1):
        try:
            ArticleTokenizationCache.ensure_populated(db.session, article)
            warmed += 1
        except Exception as e:
            failed += 1
            print(f"  ! article {article.id}: {e}")
            db.session.rollback()
            continue
        if i % COMMIT_EVERY == 0:
            db.session.commit()
            print(f"  ... {i}/{len(articles)} processed ({warmed} warmed, {failed} failed)")

    db.session.commit()
    print(f"Done. Warmed {warmed}, failed {failed}, total {len(articles)}.")


if __name__ == "__main__":
    main()
