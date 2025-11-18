#!/usr/bin/env python

"""
Tool to scan existing articles and tag low-quality ones based on quality filter rules.

This uses pattern matching and ML models (TFIDF) - does NOT call expensive LLMs.

Usage:
    python -m tools.mark_broken_articles [options]

Options:
    --dry-run          Show what would be tagged without modifying database
    --limit N          Only process N articles (for testing)
    --language CODE    Only process articles in specific language (e.g., 'da', 'fr')
    --days N           Only process articles from last N days (default: 30, use 0 for all time)
    --all              Process all articles including already broken ones
    --no-stats         Don't show detailed statistics

Examples:
    # Dry run on last 30 days of Danish articles
    python -m tools.mark_broken_articles --dry-run --language da

    # Actually tag last 7 days
    python -m tools.mark_broken_articles --days 7

    # Test on 100 articles
    python -m tools.mark_broken_articles --dry-run --limit 100
"""

import sys
import argparse
from collections import defaultdict
from datetime import datetime, timedelta

from zeeguu.api.app import create_app
from zeeguu.core.model import Article, Language, db
from zeeguu.core.model.article_broken_code_map import LowQualityTypes, ArticleBrokenMap
from zeeguu.core.content_quality.quality_filter import sufficient_quality_html, sufficient_quality_plain_text


# Mock newspaper.Article object to pass to quality filter
class MockArticle:
    def __init__(self, html, text):
        self.html = html
        self.text = text


def tag_low_quality_articles(
    dry_run=True,
    limit=None,
    language_code=None,
    untagged_only=True,
    show_stats=True,
    days_back=None,
):
    """
    Scan existing articles and tag low-quality ones using pattern and ML detection.

    Does NOT use LLMs - only pattern matching and TFIDF ML models.

    Args:
        dry_run: If True, don't modify database
        limit: Maximum number of articles to process
        language_code: Only process specific language
        untagged_only: Only process articles not marked as broken
        show_stats: Print detailed statistics
        days_back: Only process articles from last N days
    """

    print("=" * 80)
    print("LOW QUALITY ARTICLE TAGGING TOOL")
    print("=" * 80)
    print("NOTE: Uses pattern matching + ML models only (NO expensive LLM calls)")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will modify DB)'}")
    print(f"Limit: {limit if limit else 'None (all articles)'}")
    print(f"Language filter: {language_code if language_code else 'All languages'}")
    print(f"Untagged only: {untagged_only}")
    print(f"Time range: {'Last %d days' % days_back if days_back else 'All time'}")
    print("-" * 80)

    # Build query
    query = Article.query

    # CRITICAL: Exclude simplified articles and user-uploaded content
    query = query.filter(Article.parent_article_id == None)  # Not a simplified version
    query = query.filter(Article.uploader_id == None)  # Not user-uploaded

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
        "detected_low_quality": 0,
        "already_tagged": 0,
    }

    detection_reasons = defaultdict(int)
    detected_articles = []

    for i, article in enumerate(articles):
        if (i + 1) % 100 == 0:
            print(f"Progress: {i + 1}/{len(articles)} articles processed... (detected: {stats['detected_low_quality']})")

        stats["total_processed"] += 1

        # Check if already tagged with any low quality code
        existing_tag = (
            ArticleBrokenMap.query.filter(
                ArticleBrokenMap.article_id == article.id
            )
            .first()
        )

        if existing_tag:
            stats["already_tagged"] += 1
            continue

        # Run quality checks (pattern-based and ML model only, no LLMs)
        try:
            # Create mock article object
            mock_article = MockArticle(
                html=article.htmlContent or "",
                text=article.get_content()
            )

            # Check HTML quality
            is_good, reason, code = sufficient_quality_html(mock_article.html)

            if not is_good:
                stats["detected_low_quality"] += 1
                detection_reasons[code] += 1

                detected_articles.append({
                    "id": article.id,
                    "title": article.title,
                    "url": article.url.as_string() if article.url else None,
                    "reason": reason,
                    "code": code,
                    "published": article.published_time,
                })

                # Tag the article (unless dry run)
                if not dry_run:
                    try:
                        article.set_as_broken(db.session, code)
                        print(f"✓ Tagged article {article.id} ({code}): {article.title[:60]}...")
                    except Exception as e:
                        print(f"✗ Failed to tag article {article.id}: {e}")
                else:
                    print(f"[DRY RUN] Would tag article {article.id} ({code}): {article.title[:60]}...")

                continue

            # Check plain text quality
            lang_code = article.language.code if article.language else None
            is_good, reason, code = sufficient_quality_plain_text(mock_article.text, lang_code)

            if not is_good:
                stats["detected_low_quality"] += 1
                detection_reasons[code] += 1

                detected_articles.append({
                    "id": article.id,
                    "title": article.title,
                    "url": article.url.as_string() if article.url else None,
                    "reason": reason,
                    "code": code,
                    "published": article.published_time,
                })

                # Tag the article (unless dry run)
                if not dry_run:
                    try:
                        article.set_as_broken(db.session, code)
                        print(f"✓ Tagged article {article.id} ({code}): {article.title[:60]}...")
                    except Exception as e:
                        print(f"✗ Failed to tag article {article.id}: {e}")
                else:
                    print(f"[DRY RUN] Would tag article {article.id} ({code}): {article.title[:60]}...")

        except Exception as e:
            print(f"⚠ Error processing article {article.id}: {e}")
            continue

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total articles processed: {stats['total_processed']}")
    print(f"Already tagged (skipped): {stats['already_tagged']}")
    print(f"Detected low quality: {stats['detected_low_quality']}")

    if stats['total_processed'] > 0:
        detection_rate = (stats['detected_low_quality'] / (stats['total_processed'] - stats['already_tagged']) * 100) if (stats['total_processed'] - stats['already_tagged']) > 0 else 0
        print(f"Detection rate: {detection_rate:.1f}%")

    if show_stats and detection_reasons:
        print(f"\n" + "-" * 80)
        print("DETECTION REASONS BREAKDOWN")
        print("-" * 80)
        for code, count in sorted(
            detection_reasons.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / stats['detected_low_quality'] * 100) if stats['detected_low_quality'] > 0 else 0
            print(f"  {code}: {count} ({percentage:.1f}%)")

    if show_stats and detected_articles:
        print(f"\n" + "-" * 80)
        print(f"SAMPLE DETECTED ARTICLES (first 10)")
        print("-" * 80)
        for article in detected_articles[:10]:
            print(f"\nID: {article['id']}")
            print(f"Title: {article['title']}")
            print(f"URL: {article['url']}")
            print(f"Code: {article['code']}")
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
        description="Tag existing articles as low quality based on pattern and ML detection (no LLMs)"
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
        "--language", type=str, help="Only process articles in specific language (e.g., 'da', 'fr')"
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
        help="Only process articles from last N days (default: 30, use 0 for all time)",
    )

    args = parser.parse_args()

    # Create Flask app context
    app = create_app()
    with app.app_context():
        tag_low_quality_articles(
            dry_run=args.dry_run,
            limit=args.limit,
            language_code=args.language,
            untagged_only=not args.all,
            show_stats=not args.no_stats,
            days_back=args.days if args.days > 0 else None,
        )


if __name__ == "__main__":
    main()
