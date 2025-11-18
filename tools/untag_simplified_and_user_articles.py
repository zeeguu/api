#!/usr/bin/env python

"""
Clean up simplified and user-uploaded articles that were incorrectly tagged as broken.

This script finds articles that:
- Are simplified versions (have parent_article_id)
- Are user-uploaded (have uploader_id)
- Are currently marked as broken

And removes their broken tags.

Usage:
    python -m tools.untag_simplified_and_user_articles [--dry-run]
"""

import argparse
from zeeguu.api.app import create_app
from zeeguu.core.model import Article, db
from zeeguu.core.model.article_broken_code_map import ArticleBrokenMap

app = create_app()
app.app_context().push()


def cleanup_incorrectly_tagged_articles(dry_run=True):
    """
    Find and clean up simplified/user articles that were incorrectly tagged as broken.
    """

    print("=" * 80)
    print("CLEANUP: Simplified & User-Uploaded Articles")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will modify DB)'}")
    print("-" * 80)

    # Find simplified articles that are marked as broken
    simplified_broken = (
        Article.query
        .filter(Article.parent_article_id != None)
        .filter(Article.broken != 0)
        .all()
    )

    # Find user-uploaded articles that are marked as broken
    user_uploaded_broken = (
        Article.query
        .filter(Article.uploader_id != None)
        .filter(Article.broken != 0)
        .all()
    )

    print(f"\nFound {len(simplified_broken)} simplified articles marked as broken")
    print(f"Found {len(user_uploaded_broken)} user-uploaded articles marked as broken")
    print(f"Total to clean: {len(simplified_broken) + len(user_uploaded_broken)}")

    if not dry_run:
        print("\nCleaning up...")

    cleaned_count = 0

    # Clean simplified articles
    for article in simplified_broken:
        if dry_run:
            print(f"[DRY RUN] Would unmark simplified article {article.id}: {article.title[:60]}...")
        else:
            # Remove broken map entries
            ArticleBrokenMap.query.filter(
                ArticleBrokenMap.article_id == article.id
            ).delete()

            # Reset broken flag
            article.broken = 0
            db.session.add(article)
            cleaned_count += 1
            print(f"✓ Unmarked simplified article {article.id}: {article.title[:60]}...")

    # Clean user-uploaded articles
    for article in user_uploaded_broken:
        if dry_run:
            print(f"[DRY RUN] Would unmark user-uploaded article {article.id}: {article.title[:60]}...")
        else:
            # Remove broken map entries
            ArticleBrokenMap.query.filter(
                ArticleBrokenMap.article_id == article.id
            ).delete()

            # Reset broken flag
            article.broken = 0
            db.session.add(article)
            cleaned_count += 1
            print(f"✓ Unmarked user-uploaded article {article.id}: {article.title[:60]}...")

    if not dry_run:
        db.session.commit()
        print(f"\n✓ Successfully cleaned {cleaned_count} articles")

    print("\n" + "=" * 80)
    if dry_run:
        print("DRY RUN - No changes were made")
        print("Run without --dry-run to actually clean up the articles")
    else:
        print("CLEANUP COMPLETE")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Clean up simplified/user articles incorrectly tagged as broken"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be cleaned without modifying database (default: True)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the cleanup (overrides --dry-run)",
    )

    args = parser.parse_args()

    # If --execute is specified, turn off dry-run
    dry_run = not args.execute

    cleanup_incorrectly_tagged_articles(dry_run=dry_run)


if __name__ == "__main__":
    main()
