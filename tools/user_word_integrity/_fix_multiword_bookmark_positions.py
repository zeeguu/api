#!/usr/bin/env python
"""
Fix multi-word bookmark positions.

This script finds and fixes bookmarks where the token_i/sentence_i position
is incorrect for multi-word phrases. This can cause highlighting issues in exercises.

Example: Word "ikke engang" (2 tokens) at position token_i=12 when it should be token_i=11
         Results in only "engang" being highlighted instead of "ikke engang"
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


def find_incorrect_positions(limit=None):
    """
    Find all multi-word bookmarks with incorrect token positions.

    Args:
        limit: Optional limit on number of bookmarks to check

    Returns:
        List of dicts with bookmark info and correct positions
    """
    # Get all bookmarks with multi-word phrases (total_tokens > 1 or NULL)
    # Note: NULL total_tokens might also be multi-word (before the feature was added)
    query = Bookmark.query.filter(
        (Bookmark.total_tokens > 1) | (Bookmark.total_tokens == None)
    )

    if limit:
        query = query.limit(limit)

    bookmarks = query.all()

    print(f"Checking {len(bookmarks)} potentially multi-word bookmarks...")
    print()

    incorrect_bookmarks = []
    checked = 0
    errors = 0

    for bookmark in bookmarks:
        checked += 1
        if checked % 100 == 0:
            print(f"Progress: {checked}/{len(bookmarks)} checked, {len(incorrect_bookmarks)} incorrect found")

        try:
            word = bookmark.user_word.meaning.origin.content
            context = bookmark.context.get_content()
            language = bookmark.user_word.meaning.origin.language

            validation = validate_single_occurrence(word, context, language)

            if not validation['valid']:
                # Skip bookmarks where word doesn't appear in context or appears multiple times
                continue

            correct_token_i = validation['position_data']['token_i']
            correct_sentence_i = validation['position_data']['sentence_i']
            correct_total_tokens = validation['position_data']['total_tokens']

            needs_fix = False
            changes = []

            if bookmark.token_i != correct_token_i:
                needs_fix = True
                changes.append(f"token_i: {bookmark.token_i} → {correct_token_i}")

            if bookmark.sentence_i != correct_sentence_i:
                needs_fix = True
                changes.append(f"sentence_i: {bookmark.sentence_i} → {correct_sentence_i}")

            if bookmark.total_tokens != correct_total_tokens:
                needs_fix = True
                changes.append(f"total_tokens: {bookmark.total_tokens} → {correct_total_tokens}")

            if needs_fix:
                incorrect_bookmarks.append({
                    'bookmark': bookmark,
                    'word': word,
                    'context': context[:80] + '...' if len(context) > 80 else context,
                    'changes': changes,
                    'correct_sentence_i': correct_sentence_i,
                    'correct_token_i': correct_token_i,
                    'correct_total_tokens': correct_total_tokens,
                })

        except Exception as e:
            errors += 1
            if errors <= 5:  # Only show first 5 errors
                print(f"  Error checking bookmark {bookmark.id}: {e}")
            continue

    print(f"\nChecked {checked} bookmarks")
    if errors > 0:
        print(f"Errors encountered: {errors} (word not found in context or multiple occurrences)")
    print()

    return incorrect_bookmarks


def print_incorrect_bookmarks(incorrect_bookmarks, limit=20):
    """Print information about incorrect bookmarks."""
    if not incorrect_bookmarks:
        print("✓ No incorrect bookmark positions found!")
        return

    print(f"="*80)
    print(f"Found {len(incorrect_bookmarks)} bookmarks with incorrect positions")
    print(f"="*80)
    print()

    for i, item in enumerate(incorrect_bookmarks[:limit]):
        print(f"Bookmark {item['bookmark'].id}: '{item['word']}'")
        print(f"  Context: {item['context']}")
        print(f"  Changes needed:")
        for change in item['changes']:
            print(f"    - {change}")
        print()

    if len(incorrect_bookmarks) > limit:
        print(f"... and {len(incorrect_bookmarks) - limit} more")
        print()


def fix_bookmark_positions(incorrect_bookmarks, dry_run=True):
    """
    Fix incorrect bookmark positions.

    Args:
        incorrect_bookmarks: List of dicts from find_incorrect_positions()
        dry_run: If True, only show what would be fixed

    Returns:
        Number of bookmarks fixed
    """
    if not incorrect_bookmarks:
        return 0

    if dry_run:
        print(f"[DRY RUN] Would fix {len(incorrect_bookmarks)} bookmarks")
        return 0

    print(f"Fixing {len(incorrect_bookmarks)} bookmarks...")
    fixed = 0

    for item in incorrect_bookmarks:
        bookmark = item['bookmark']

        try:
            bookmark.sentence_i = item['correct_sentence_i']
            bookmark.token_i = item['correct_token_i']
            bookmark.total_tokens = item['correct_total_tokens']

            db.session.add(bookmark)
            fixed += 1

            if fixed % 100 == 0:
                print(f"  Fixed {fixed}/{len(incorrect_bookmarks)}...")

        except Exception as e:
            print(f"  ✗ Error fixing bookmark {bookmark.id}: {e}")
            continue

    try:
        db.session.commit()
        print(f"\n✓ Successfully fixed {fixed} bookmarks")
        return fixed
    except Exception as e:
        db.session.rollback()
        print(f"\n✗ Error committing fixes: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Find and fix multi-word bookmarks with incorrect token positions"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Actually fix the positions (default is dry-run)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of bookmarks to check (for testing)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all incorrect bookmarks (default: show first 20)"
    )

    args = parser.parse_args()

    # Find incorrect bookmarks
    incorrect_bookmarks = find_incorrect_positions(limit=args.limit)

    # Print results
    if args.verbose:
        print_incorrect_bookmarks(incorrect_bookmarks, limit=len(incorrect_bookmarks))
    else:
        print_incorrect_bookmarks(incorrect_bookmarks, limit=20)

    # Fix if requested
    if args.fix:
        if not incorrect_bookmarks:
            return

        response = input(f"\n⚠️  Fix {len(incorrect_bookmarks)} bookmarks? [y/N]: ")
        if response.lower() != 'y':
            print("Fix cancelled.")
            return

        fix_bookmark_positions(incorrect_bookmarks, dry_run=False)
    else:
        if incorrect_bookmarks:
            print("💡 Run with --fix to actually fix these bookmarks")
            print("   Example: python -m tools.user_word_integrity._fix_multiword_bookmark_positions --fix")


if __name__ == "__main__":
    main()
