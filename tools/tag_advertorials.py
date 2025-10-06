#!/usr/bin/env python

"""
Tool to scan existing articles and tag advertorials based on URL patterns and keywords.

This helps:
1. Identify existing advertorials in the database
2. Fine-tune detection patterns by reviewing tagged articles
3. Clean up existing data before new rules are applied

Usage:
    python -m tools.tag_advertorials [options]

Options:
    --dry-run          Show what would be tagged without modifying database
    --limit N          Only process N articles (for testing)
    --language CODE    Only process articles in specific language (e.g., 'fr')
    --days N           Only process articles from last N days (default: 30, use 0 for all time)
    --all              Process all articles including already broken ones
    --no-stats         Don't show detailed statistics

Examples:
    # Dry run on last 30 days of French articles
    python -m tools.tag_advertorials --dry-run --language fr

    # Actually tag last 7 days
    python -m tools.tag_advertorials --language fr --days 7

    # Test on 100 articles
    python -m tools.tag_advertorials --dry-run --limit 100
"""

import sys
import argparse
from collections import defaultdict
from datetime import datetime, timedelta

from zeeguu.api.app import create_app
from zeeguu.core.model import Article, Language, Url, db
from zeeguu.core.model.article_broken_code_map import LowQualityTypes, ArticleBrokenMap
from zeeguu.core.content_quality.advertorial_detection import is_advertorial


def tag_existing_advertorials(
    dry_run=True,
    limit=None,
    language_code=None,
    untagged_only=True,
    show_stats=True,
    days_back=None,
):
    """
    Scan existing articles and tag advertorials.

    Args:
        dry_run: If True, don't modify database
        limit: Maximum number of articles to process
        language_code: Only process specific language
        untagged_only: Only process articles not marked as broken
        show_stats: Print detailed statistics
        days_back: Only process articles from last N days
    """

    print("=" * 80)
    print("ADVERTORIAL TAGGING TOOL")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will modify DB)'}")
    print(f"Limit: {limit if limit else 'None (all articles)'}")
    print(f"Language filter: {language_code if language_code else 'All languages'}")
    print(f"Untagged only: {untagged_only}")
    print(f"Time range: {'Last %d days' % days_back if days_back else 'All time'}")
    print("-" * 80)

    # Build query
    query = Article.query

    if language_code:
        language = Language.find(language_code)
        if not language:
            print(f"ERROR: Language '{language_code}' not found")
            return
        query = query.filter(Article.language_id == language.id)

    if untagged_only:
        # Only get articles that are not marked as broken (broken = 0 or NULL)
        query = query.filter((Article.broken == 0) | (Article.broken == None))

    if days_back:
        # Only get articles from last N days
        cutoff_date = datetime.now() - timedelta(days=days_back)
        query = query.filter(Article.published_time >= cutoff_date)
        print(f"Filtering articles published after: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")

    # Order by most recent first
    query = query.order_by(Article.published_time.desc())

    if limit:
        query = query.limit(limit)

    articles = query.all()

    print(f"\nProcessing {len(articles)} articles...\n")

    # Statistics
    stats = {
        "total_processed": 0,
        "detected_advertorials": 0,
        "url_pattern_matches": 0,
        "title_keyword_matches": 0,
        "multiple_keyword_matches": 0,
        "already_tagged": 0,
    }

    detection_reasons = defaultdict(int)
    detected_articles = []

    for i, article in enumerate(articles):
        if (i + 1) % 50 == 0:
            print(f"Progress: {i + 1}/{len(articles)} articles processed... (detected: {stats['detected_advertorials']})")

        stats["total_processed"] += 1

        # Get article URL
        url_string = article.url.as_string() if article.url else None

        # Check if already tagged as advertorial
        existing_tag = (
            ArticleBrokenMap.query.filter(
                ArticleBrokenMap.article_id == article.id,
                ArticleBrokenMap.broken_code == LowQualityTypes.ADVERTORIAL,
            )
            .first()
        )

        if existing_tag:
            stats["already_tagged"] += 1
            continue

        # Check if advertorial
        is_advert, reason = is_advertorial(
            url=url_string,
            title=article.title,
            content=article.get_content()[:1000],  # Only check first 1000 chars
        )

        if is_advert:
            stats["detected_advertorials"] += 1
            detection_reasons[reason] += 1

            # Track specific detection types
            if "URL" in reason:
                stats["url_pattern_matches"] += 1
            elif "Title" in reason:
                stats["title_keyword_matches"] += 1
            elif "Multiple" in reason:
                stats["multiple_keyword_matches"] += 1

            detected_articles.append(
                {
                    "id": article.id,
                    "title": article.title,
                    "url": url_string,
                    "reason": reason,
                    "published": article.published_time,
                }
            )

            # Tag the article (unless dry run)
            if not dry_run:
                try:
                    article.set_as_broken(db.session, LowQualityTypes.ADVERTORIAL)
                    print(f"✓ Tagged article {article.id}: {article.title[:60]}...")
                except Exception as e:
                    print(
                        f"✗ Failed to tag article {article.id}: {e}"
                    )
            else:
                print(f"[DRY RUN] Would tag article {article.id}: {article.title[:60]}... ({reason})")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total articles processed: {stats['total_processed']}")
    print(f"Detected advertorials: {stats['detected_advertorials']}")
    print(f"Already tagged: {stats['already_tagged']}")
    print(f"\nDetection breakdown:")
    print(f"  - URL pattern matches: {stats['url_pattern_matches']}")
    print(f"  - Title keyword matches: {stats['title_keyword_matches']}")
    print(f"  - Multiple keyword matches: {stats['multiple_keyword_matches']}")

    if show_stats and detected_articles:
        print(f"\n" + "-" * 80)
        print("DETECTION REASONS BREAKDOWN")
        print("-" * 80)
        for reason, count in sorted(
            detection_reasons.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {reason}: {count}")

        print(f"\n" + "-" * 80)
        print(f"SAMPLE DETECTED ARTICLES (first 10)")
        print("-" * 80)
        for article in detected_articles[:10]:
            print(f"\nID: {article['id']}")
            print(f"Title: {article['title']}")
            print(f"URL: {article['url']}")
            print(f"Reason: {article['reason']}")
            print(f"Published: {article['published']}")

    if dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN MODE - No changes were made to the database")
        print("Run without --dry-run to actually tag articles")
        print("=" * 80)

    return detected_articles


def main():
    parser = argparse.ArgumentParser(
        description="Tag existing articles as advertorials based on detection patterns"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be tagged without modifying database",
    )
    parser.add_argument(
        "--limit", type=int, help="Only process N articles (for testing)"
    )
    parser.add_argument(
        "--language", type=str, help="Only process articles in specific language (e.g., 'fr')"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all articles including already broken ones",
    )
    parser.add_argument(
        "--no-stats", action="store_true", help="Don't show detailed statistics"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Only process articles from last N days (default: 30)",
    )

    args = parser.parse_args()

    # Create Flask app context
    app = create_app()
    with app.app_context():
        tag_existing_advertorials(
            dry_run=args.dry_run,
            limit=args.limit,
            language_code=args.language,
            untagged_only=not args.all,
            show_stats=not args.no_stats,
            days_back=args.days,
        )


if __name__ == "__main__":
    main()
