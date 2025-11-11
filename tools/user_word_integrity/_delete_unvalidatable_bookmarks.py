#!/usr/bin/env python
"""
Delete bookmarks that cannot be validated.

This script finds and deletes bookmarks where the word cannot be found in the context
or appears multiple times. These bookmarks cannot have their position data fixed and
would produce incorrect highlighting.

This is a cleanup script to prepare for applying NOT NULL constraints.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# REQUIRED: Initialize Flask app context for database access
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import Bookmark
from zeeguu.core.tokenization.word_position_finder import validate_single_occurrence
import argparse


def find_unvalidatable_bookmarks():
    """
    Find all bookmarks that cannot be validated.

    Returns:
        List of dicts with bookmark info and reason
    """
    # Get all bookmarks with NULL position data
    query = Bookmark.query.filter(
        (Bookmark.token_i == None) |
        (Bookmark.sentence_i == None) |
        (Bookmark.total_tokens == None)
    )

    bookmarks = query.all()

    print(f"Checking {len(bookmarks)} bookmarks with NULL positions...")
    print()

    unvalidatable = []
    checked = 0

    for bookmark in bookmarks:
        checked += 1
        if checked % 10 == 0:
            print(f"Progress: {checked}/{len(bookmarks)} checked")

        try:
            word = bookmark.user_word.meaning.origin.content
            context = bookmark.context.get_content()
            language = bookmark.user_word.meaning.origin.language

            validation = validate_single_occurrence(word, context, language)

            if not validation['valid']:
                # validation returns {'valid': False, 'error_type': 'reason', 'error_message': 'details'}
                error_type = validation.get('error_type', 'unknown')
                reason = f"{error_type}: {validation.get('error_message', 'Unknown error')[:50]}"
                unvalidatable.append({
                    'bookmark': bookmark,
                    'word': word,
                    'context': context[:80] + '...' if len(context) > 80 else context,
                    'reason': reason,
                    'user_id': bookmark.user_word.user.id,
                    'created': bookmark.time.strftime('%Y-%m-%d') if bookmark.time else 'Unknown',
                })

        except Exception as e:
            try:
                user_id = bookmark.user_word.user.id if bookmark.user_word and bookmark.user_word.user else 'Unknown'
            except:
                user_id = 'Unknown'

            unvalidatable.append({
                'bookmark': bookmark,
                'word': 'ERROR',
                'context': str(e)[:80],
                'reason': f'Error: {str(e)[:50]}',
                'user_id': user_id,
                'created': bookmark.time.strftime('%Y-%m-%d') if bookmark.time else 'Unknown',
            })
            continue

    print(f"\nChecked {checked} bookmarks")
    print()

    return unvalidatable


def print_unvalidatable_bookmarks(unvalidatable):
    """Print information about unvalidatable bookmarks."""
    if not unvalidatable:
        print("✓ No unvalidatable bookmarks found!")
        return

    print(f"="*80)
    print(f"Found {len(unvalidatable)} unvalidatable bookmarks")
    print(f"="*80)
    print()

    for item in unvalidatable:
        print(f"Bookmark {item['bookmark'].id}: '{item['word']}' (User {item['user_id']}, {item['created']})")
        print(f"  Context: {item['context']}")
        print(f"  Reason: {item['reason']}")
        print()


def delete_bookmarks(unvalidatable, dry_run=True):
    """
    Delete unvalidatable bookmarks.

    Args:
        unvalidatable: List of dicts from find_unvalidatable_bookmarks()
        dry_run: If True, only show what would be deleted

    Returns:
        Number of bookmarks deleted
    """
    if not unvalidatable:
        return 0

    if dry_run:
        print(f"[DRY RUN] Would delete {len(unvalidatable)} bookmarks")
        return 0

    print(f"Deleting {len(unvalidatable)} bookmarks...")

    # Step 1: Clear any preferred_bookmark_id references
    from zeeguu.core.model.user_word import UserWord
    print("  Step 1: Clearing preferred_bookmark_id references...")
    cleared = 0
    for item in unvalidatable:
        bookmark = item['bookmark']
        # Find any UserWords that reference this bookmark as preferred
        user_words_referencing = UserWord.query.filter_by(preferred_bookmark_id=bookmark.id).all()
        for uw in user_words_referencing:
            uw.preferred_bookmark_id = None
            db.session.add(uw)
            cleared += 1

    if cleared > 0:
        db.session.commit()
        print(f"  Cleared {cleared} preferred_bookmark_id references")

    # Step 2: Delete the bookmarks
    print("  Step 2: Deleting bookmarks...")
    deleted = 0

    for item in unvalidatable:
        bookmark = item['bookmark']

        try:
            db.session.delete(bookmark)
            deleted += 1

            if deleted % 10 == 0:
                print(f"  Deleted {deleted}/{len(unvalidatable)}...")

        except Exception as e:
            print(f"  ✗ Error deleting bookmark {bookmark.id}: {e}")
            continue

    try:
        db.session.commit()
        print(f"\n✓ Successfully deleted {deleted} bookmarks")
        return deleted
    except Exception as e:
        db.session.rollback()
        print(f"\n✗ Error committing deletions: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Find and delete bookmarks that cannot be validated"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete the bookmarks (default is dry-run)"
    )

    args = parser.parse_args()

    # Find unvalidatable bookmarks
    unvalidatable = find_unvalidatable_bookmarks()

    # Print results
    print_unvalidatable_bookmarks(unvalidatable)

    # Delete if requested
    if args.delete:
        if not unvalidatable:
            return

        response = input(f"\n⚠️  Delete {len(unvalidatable)} unvalidatable bookmarks? This cannot be undone! [y/N]: ")
        if response.lower() != 'y':
            print("Delete cancelled.")
            return

        delete_bookmarks(unvalidatable, dry_run=False)

        # Verify deletion
        print("\nVerifying deletion...")
        remaining = Bookmark.query.filter(
            (Bookmark.token_i == None) |
            (Bookmark.sentence_i == None) |
            (Bookmark.total_tokens == None)
        ).count()

        if remaining == 0:
            print("✓ All unvalidatable bookmarks deleted!")
            print("\nYou can now apply the database migration:")
            print("  mysql -u zeeguu_test -pzeeguu_test zeeguu_test < tools/migrations/25-11-11--add-bookmark-position-constraints.sql")
        else:
            print(f"⚠️  Warning: {remaining} bookmarks with NULL positions still remain")
    else:
        if unvalidatable:
            print("💡 Run with --delete to actually delete these bookmarks")
            print("   Example: python -m tools.user_word_integrity._delete_unvalidatable_bookmarks --delete")


if __name__ == "__main__":
    main()
