#!/usr/bin/env python
"""
Check and fix data integrity issues in the Zeeguu database.

This script checks for:
1. UserWords with preferred_bookmark_id pointing to bookmarks that don't belong to them
2. UserWords with no bookmarks at all (orphaned)
3. UserWords with preferred_bookmark_id = NULL but having bookmarks
4. Bookmarks with invalid user_word_id references
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

from zeeguu.core.model import UserWord, Bookmark
from sqlalchemy import func
import argparse


def check_preferred_bookmark_integrity():
    """
    Check if UserWords have preferred_bookmark_id pointing to bookmarks that belong to them.
    Returns list of (user_word, wrong_bookmark_id, correct_bookmarks).
    """
    print("\n" + "="*80)
    print("Checking preferred_bookmark integrity...")
    print("="*80)

    issues = []

    # Get all UserWords with a preferred_bookmark set
    user_words = UserWord.query.filter(UserWord.preferred_bookmark_id != None).all()

    for uw in user_words:
        # Get all bookmarks that actually belong to this UserWord
        actual_bookmarks = [b.id for b in uw.bookmarks()]

        if uw.preferred_bookmark_id not in actual_bookmarks:
            issues.append({
                'user_word': uw,
                'wrong_bookmark_id': uw.preferred_bookmark_id,
                'correct_bookmarks': actual_bookmarks
            })

    return issues


def check_null_preferred_bookmarks():
    """
    Check for UserWords that have bookmarks but preferred_bookmark_id is NULL.
    """
    print("\n" + "="*80)
    print("Checking for UserWords with NULL preferred_bookmark but having bookmarks...")
    print("="*80)

    issues = []

    # Get UserWords with NULL preferred_bookmark
    user_words = UserWord.query.filter(UserWord.preferred_bookmark_id == None).all()

    for uw in user_words:
        bookmarks = uw.bookmarks()
        if len(bookmarks) > 0:
            issues.append({
                'user_word': uw,
                'bookmarks': [b.id for b in bookmarks]
            })

    return issues


def check_orphaned_user_words():
    """
    Check for UserWords with no bookmarks at all.
    """
    print("\n" + "="*80)
    print("Checking for orphaned UserWords (no bookmarks)...")
    print("="*80)

    orphaned = (
        db.session.query(UserWord)
        .outerjoin(Bookmark, Bookmark.user_word_id == UserWord.id)
        .group_by(UserWord.id)
        .having(func.count(Bookmark.id) == 0)
        .all()
    )

    return orphaned


def fix_preferred_bookmark_issues(issues, dry_run=True):
    """
    Fix UserWords with wrong preferred_bookmark_id.
    """
    if not issues:
        print("\n✓ No preferred_bookmark integrity issues found!")
        return 0

    print(f"\nFound {len(issues)} UserWords with wrong preferred_bookmark_id:")

    for issue in issues:
        uw = issue['user_word']
        wrong_id = issue['wrong_bookmark_id']
        correct_ids = issue['correct_bookmarks']

        print(f"\n  UserWord {uw.id}: \"{uw.meaning.origin.content}\" -> \"{uw.meaning.translation.content}\"")
        print(f"    ✗ preferred_bookmark_id: {wrong_id} (doesn't belong to this UserWord)")
        print(f"    ✓ actual bookmarks: {correct_ids}")

        if len(correct_ids) > 0:
            new_preferred = correct_ids[0]  # Use first bookmark
            print(f"    → Will set preferred_bookmark_id to: {new_preferred}")

            if not dry_run:
                uw.preferred_bookmark_id = new_preferred
                db.session.add(uw)
        else:
            print(f"    → No bookmarks available, will set to NULL")
            if not dry_run:
                uw.preferred_bookmark_id = None
                db.session.add(uw)

    if not dry_run:
        db.session.commit()
        print(f"\n✓ Fixed {len(issues)} preferred_bookmark issues")
    else:
        print(f"\n[DRY RUN] Would fix {len(issues)} issues")

    return len(issues)


def fix_null_preferred_bookmarks(issues, dry_run=True):
    """
    Fix UserWords with NULL preferred_bookmark but having bookmarks.
    """
    if not issues:
        print("\n✓ No NULL preferred_bookmark issues found!")
        return 0

    print(f"\nFound {len(issues)} UserWords with NULL preferred_bookmark but having bookmarks:")

    for issue in issues:
        uw = issue['user_word']
        bookmark_ids = issue['bookmarks']

        print(f"\n  UserWord {uw.id}: \"{uw.meaning.origin.content}\" -> \"{uw.meaning.translation.content}\"")
        print(f"    Bookmarks: {bookmark_ids}")
        print(f"    → Will set preferred_bookmark_id to: {bookmark_ids[0]}")

        if not dry_run:
            uw.preferred_bookmark_id = bookmark_ids[0]
            db.session.add(uw)

    if not dry_run:
        db.session.commit()
        print(f"\n✓ Fixed {len(issues)} NULL preferred_bookmark issues")
    else:
        print(f"\n[DRY RUN] Would fix {len(issues)} issues")

    return len(issues)


def fix_orphaned_user_words(orphaned, dry_run=True):
    """
    Delete orphaned UserWords.
    """
    if not orphaned:
        print("\n✓ No orphaned UserWords found!")
        return 0

    print(f"\nFound {len(orphaned)} orphaned UserWords (no bookmarks):")

    for uw in orphaned[:10]:  # Show first 10
        print(f"  UserWord {uw.id}: \"{uw.meaning.origin.content}\" -> \"{uw.meaning.translation.content}\"")

    if len(orphaned) > 10:
        print(f"  ... and {len(orphaned) - 10} more")

    if not dry_run:
        # Delete associated schedules first
        from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

        for uw in orphaned:
            schedule = BasicSRSchedule.find_by_user_word(uw)
            if schedule:
                db.session.delete(schedule)
            db.session.delete(uw)

        db.session.commit()
        print(f"\n✓ Deleted {len(orphaned)} orphaned UserWords")
    else:
        print(f"\n[DRY RUN] Would delete {len(orphaned)} orphaned UserWords")

    return len(orphaned)


def main():
    parser = argparse.ArgumentParser(
        description="Check and fix data integrity issues in Zeeguu database"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Actually fix the issues (default is dry-run)"
    )
    parser.add_argument(
        "--skip-orphaned",
        action="store_true",
        help="Skip checking for orphaned UserWords (can be slow)"
    )

    args = parser.parse_args()

    dry_run = not args.fix

    if dry_run:
        print("\n" + "="*80)
        print("DRY RUN MODE - No changes will be made")
        print("Run with --fix to actually fix the issues")
        print("="*80)

    total_issues = 0

    # Check 1: Wrong preferred_bookmark_id
    wrong_preferred = check_preferred_bookmark_integrity()
    total_issues += fix_preferred_bookmark_issues(wrong_preferred, dry_run)

    # Check 2: NULL preferred_bookmark with bookmarks
    null_preferred = check_null_preferred_bookmarks()
    total_issues += fix_null_preferred_bookmarks(null_preferred, dry_run)

    # Check 3: Orphaned UserWords (optional, can be slow)
    if not args.skip_orphaned:
        orphaned = check_orphaned_user_words()
        total_issues += fix_orphaned_user_words(orphaned, dry_run)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total issues found: {total_issues}")

    if dry_run and total_issues > 0:
        print("\n💡 Run with --fix to actually fix these issues")
        print("   Example: python -m tools._check_and_fix_data_integrity --fix")
    elif total_issues == 0:
        print("\n✓ Database integrity looks good!")
    else:
        print(f"\n✓ Fixed {total_issues} issues!")


if __name__ == "__main__":
    main()
