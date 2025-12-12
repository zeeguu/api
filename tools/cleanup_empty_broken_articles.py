#!/usr/bin/env python
"""
Tool to delete broken articles that have no content (failed extraction).

These articles take up database space but have no value - they failed to extract
content from the source website (usually due to paywalls or site changes).

Usage:
    python -m tools.cleanup_empty_broken_articles [options]

Options:
    --dry-run           Show what would be deleted without modifying database
    --feed-id ID        Only process articles from specific feed ID
    --feed-name NAME    Only process articles from feed matching NAME (partial match)
    --min-content N     Minimum content length to keep (default: 100 chars)
    --limit N           Only delete up to N articles (for testing)

Examples:
    # Dry run to see what would be deleted
    python -m tools.cleanup_empty_broken_articles --dry-run

    # Clean up a specific feed
    python -m tools.cleanup_empty_broken_articles --feed-name "Pour la Science"

    # Clean up all feeds, keeping articles with at least 500 chars
    python -m tools.cleanup_empty_broken_articles --min-content 500
"""

import sys
import argparse
from collections import defaultdict

from zeeguu.api.app import create_app
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.feed import Feed
from zeeguu.core.model.article_broken_code_map import ArticleBrokenMap


def cleanup_empty_broken_articles(
    dry_run=True,
    feed_id=None,
    feed_name=None,
    min_content=100,
    limit=None,
):
    """
    Delete broken articles that have no/little content.

    Args:
        dry_run: If True, don't modify database
        feed_id: Only process specific feed by ID
        feed_name: Only process feeds matching this name (partial match)
        min_content: Minimum content length to keep (default 100 chars)
        limit: Maximum number of articles to delete
    """
    print("=" * 70)
    print("CLEANUP EMPTY BROKEN ARTICLES")
    print("=" * 70)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will delete)'}")
    print(f"Min content to keep: {min_content} chars")
    if feed_id:
        print(f"Feed ID filter: {feed_id}")
    if feed_name:
        print(f"Feed name filter: {feed_name}")
    if limit:
        print(f"Limit: {limit} articles")
    print("-" * 70)

    # Build feed filter
    feeds_to_process = []
    if feed_id:
        feed = Feed.query.get(feed_id)
        if feed:
            feeds_to_process = [feed]
        else:
            print(f"ERROR: Feed with ID {feed_id} not found")
            return
    elif feed_name:
        feeds_to_process = Feed.query.filter(Feed.title.like(f"%{feed_name}%")).all()
        if not feeds_to_process:
            print(f"ERROR: No feeds found matching '{feed_name}'")
            return
    else:
        # All feeds
        feeds_to_process = Feed.query.all()

    print(f"\nProcessing {len(feeds_to_process)} feed(s)...")

    total_deleted = 0
    stats_by_feed = defaultdict(lambda: {"found": 0, "deleted": 0})

    for feed in feeds_to_process:
        # Find broken articles for this feed
        broken_articles = Article.query.filter(
            Article.feed_id == feed.id,
            Article.broken > 0
        ).all()

        if not broken_articles:
            continue

        # Filter to those with no meaningful content
        to_delete = []
        for art in broken_articles:
            content_len = len(art.content) if art.content else 0
            if content_len < min_content:
                to_delete.append(art.id)
                if limit and len(to_delete) + total_deleted >= limit:
                    break

        if not to_delete:
            continue

        stats_by_feed[feed.title]["found"] = len(broken_articles)
        stats_by_feed[feed.title]["to_delete"] = len(to_delete)

        print(f"\n{feed.title}:")
        print(f"  Broken articles: {len(broken_articles)}")
        print(f"  With < {min_content} chars: {len(to_delete)}")

        if dry_run:
            # Show sample
            for art_id in to_delete[:3]:
                art = db.session.get(Article, art_id)
                content_len = len(art.content) if art.content else 0
                print(f"    Would delete: {art.id} - {art.title[:40]}... ({content_len} chars)")
            if len(to_delete) > 3:
                print(f"    ... and {len(to_delete) - 3} more")
        else:
            # Delete in batches
            batch_size = 1000
            deleted = 0
            for i in range(0, len(to_delete), batch_size):
                batch = to_delete[i:i + batch_size]

                # First delete the broken code mappings
                ArticleBrokenMap.query.filter(
                    ArticleBrokenMap.article_id.in_(batch)
                ).delete(synchronize_session=False)

                # Then delete the articles
                Article.query.filter(Article.id.in_(batch)).delete(synchronize_session=False)

                db.session.commit()
                deleted += len(batch)

            stats_by_feed[feed.title]["deleted"] = deleted
            total_deleted += deleted
            print(f"  Deleted: {deleted}")

        if limit and total_deleted >= limit:
            print(f"\nReached limit of {limit} articles")
            break

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if dry_run:
        total_would_delete = sum(s.get("to_delete", 0) for s in stats_by_feed.values())
        print(f"Would delete {total_would_delete} empty broken articles")
        print("\nRun without --dry-run to actually delete")
    else:
        print(f"Deleted {total_deleted} empty broken articles")

    return total_deleted


def main():
    parser = argparse.ArgumentParser(
        description="Delete broken articles with no content"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without modifying database",
    )
    parser.add_argument(
        "--feed-id",
        type=int,
        help="Only process articles from specific feed ID",
    )
    parser.add_argument(
        "--feed-name",
        type=str,
        help="Only process articles from feed matching NAME (partial match)",
    )
    parser.add_argument(
        "--min-content",
        type=int,
        default=100,
        help="Minimum content length to keep (default: 100 chars)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Only delete up to N articles",
    )

    args = parser.parse_args()

    app = create_app()
    app.app_context().push()

    cleanup_empty_broken_articles(
        dry_run=args.dry_run,
        feed_id=args.feed_id,
        feed_name=args.feed_name,
        min_content=args.min_content,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
