#!/usr/bin/env python
"""
Cleanup script to find and delete orphaned UserWords.

An orphaned UserWord is one that has no associated bookmarks.
These can occur from:
1. Bookmark updates that changed the word/translation (before the fix)
2. Manual bookmark deletions
3. Data inconsistencies

This script:
1. Finds all UserWords with zero bookmarks
2. Shows the user which ones will be deleted
3. Optionally deletes them (with --delete flag)
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# REQUIRED: Initialize Flask app context for database access
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import UserWord, Bookmark, User
from sqlalchemy import func
from collections import defaultdict
import argparse


def find_orphaned_user_words(user_id=None):
    """
    Find all UserWords that have no associated bookmarks.

    Args:
        user_id: Optional user ID to limit search to specific user

    Returns:
        List of orphaned UserWord objects
    """
    # Build query to find UserWords with no bookmarks
    query = (
        db.session.query(UserWord)
        .outerjoin(Bookmark, Bookmark.user_word_id == UserWord.id)
        .group_by(UserWord.id)
        .having(func.count(Bookmark.id) == 0)
    )

    if user_id:
        query = query.filter(UserWord.user_id == user_id)

    return query.all()


def analyze_orphaned_user_words(orphaned_user_words):
    """
    Analyze and group orphaned UserWords by user.

    Returns:
        Dictionary mapping user_id to list of orphaned UserWords
    """
    by_user = defaultdict(list)

    for uw in orphaned_user_words:
        by_user[uw.user_id].append(uw)

    return by_user


def print_orphaned_user_words(orphaned_user_words, verbose=False):
    """
    Print information about orphaned UserWords.
    """
    if not orphaned_user_words:
        print("\n✓ No orphaned UserWords found!")
        return

    by_user = analyze_orphaned_user_words(orphaned_user_words)

    print(f"\n{'='*80}")
    print(f"Found {len(orphaned_user_words)} orphaned UserWords across {len(by_user)} users")
    print(f"{'='*80}\n")

    for user_id, user_words in sorted(by_user.items()):
        user = User.find_by_id(user_id)
        user_name = user.name if user else "Unknown"
        user_email = user.email if user else "Unknown"

        print(f"User: {user_name} ({user_email}) - User ID: {user_id}")
        print(f"  Orphaned UserWords: {len(user_words)}")

        if verbose:
            for uw in user_words[:10]:  # Limit to first 10 for readability
                meaning = uw.meaning
                print(f"    - UserWord ID {uw.id}: \"{meaning.origin.content}\" → \"{meaning.translation.content}\"")
                print(f"      Meaning ID: {meaning.id}, Fit for study: {uw.fit_for_study}")

            if len(user_words) > 10:
                print(f"    ... and {len(user_words) - 10} more")

        print()


def delete_orphaned_user_words(orphaned_user_words, dry_run=True):
    """
    Delete orphaned UserWords.

    Args:
        orphaned_user_words: List of UserWord objects to delete
        dry_run: If True, only show what would be deleted without actually deleting
    """
    if not orphaned_user_words:
        print("No orphaned UserWords to delete.")
        return 0

    if dry_run:
        print(f"\n[DRY RUN] Would delete {len(orphaned_user_words)} orphaned UserWords")
        return 0

    print(f"\nDeleting {len(orphaned_user_words)} orphaned UserWords...")

    deleted_count = 0
    for uw in orphaned_user_words:
        try:
            # Delete associated data first (schedules and exercises)
            from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
            from zeeguu.core.model import Exercise

            # Delete schedule
            schedule = BasicSRSchedule.find_by_user_word(uw)
            if schedule:
                db.session.delete(schedule)

            # Delete exercises (must be deleted before UserWord due to NOT NULL constraint)
            exercises = Exercise.query.filter_by(user_word_id=uw.id).all()
            for ex in exercises:
                db.session.delete(ex)

            db.session.delete(uw)
            deleted_count += 1
        except Exception as e:
            print(f"  ✗ Error deleting UserWord {uw.id}: {e}")

    try:
        db.session.commit()
        print(f"\n✓ Successfully deleted {deleted_count} orphaned UserWords")
        return deleted_count
    except Exception as e:
        db.session.rollback()
        print(f"\n✗ Error committing deletions: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Find and optionally delete orphaned UserWords (UserWords with no bookmarks)"
    )
    parser.add_argument(
        "--user-id",
        type=int,
        help="Only process orphaned UserWords for this user ID"
    )
    parser.add_argument(
        "--user-email",
        type=str,
        help="Only process orphaned UserWords for this user email"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete the orphaned UserWords (default is dry-run)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed information about each orphaned UserWord"
    )

    args = parser.parse_args()

    # Determine user_id from email if provided
    user_id = args.user_id
    if args.user_email:
        user = User.query.filter_by(email=args.user_email).first()
        if not user:
            print(f"✗ User with email '{args.user_email}' not found")
            sys.exit(1)
        user_id = user.id
        print(f"Found user: {user.name} (ID: {user_id})")

    # Find orphaned UserWords
    print("\nSearching for orphaned UserWords...")
    orphaned_user_words = find_orphaned_user_words(user_id)

    # Print analysis
    print_orphaned_user_words(orphaned_user_words, verbose=args.verbose)

    # Delete if requested
    if args.delete:
        if not orphaned_user_words:
            return

        # Confirm deletion
        response = input(f"\n⚠️  Are you sure you want to delete {len(orphaned_user_words)} orphaned UserWords? [y/N]: ")
        if response.lower() != 'y':
            print("Deletion cancelled.")
            return

        delete_orphaned_user_words(orphaned_user_words, dry_run=False)
    else:
        if orphaned_user_words:
            print("\n💡 Run with --delete to actually delete these orphaned UserWords")
            print("   Example: python -m tools._cleanup_orphaned_user_words --delete")
            if not user_id:
                print("   Or for specific user: python -m tools._cleanup_orphaned_user_words --user-email i@mir.lu --delete")


if __name__ == "__main__":
    main()
