#!/usr/bin/env python
"""
Delete bookmarks where the word doesn't appear in the context.

This script finds and deletes bookmarks where the origin word cannot be found
in the bookmark's context. This typically happens due to:
- Accent/diacritic variations (orienté vs oriente)
- Verb conjugations (hatte vs hätte)
- Unicode corruption (bad vs båd)

These bookmarks cannot be properly highlighted in exercises, so they should be removed.
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

from zeeguu.core.model.bookmark import Bookmark
import unicodedata


def find_problematic_bookmarks(start_percent=95, end_percent=100):
    """
    Find all bookmarks where word does not appear in context.

    Args:
        start_percent: Start scanning from this percentage (0-100)
        end_percent: Stop scanning at this percentage (0-100)
    """
    print('Finding all bookmarks where word does not appear in context...')
    print(f'Scanning range: {start_percent}% to {end_percent}%')
    print()

    problematic_ids = []
    batch_size = 1000
    total = Bookmark.query.count()

    # Calculate offset range
    start_offset = int(total * start_percent / 100)
    end_offset = int(total * end_percent / 100)

    checked = 0

    print(f'Total bookmarks in database: {total}')
    print(f'Scanning bookmarks {start_offset} to {end_offset}')
    print()

    # Query in reverse order (highest IDs first) to find recent problematic bookmarks
    for offset in range(start_offset, end_offset, batch_size):
        bookmarks = (
            Bookmark.query
            .order_by(Bookmark.id.desc())
            .offset(offset - start_offset)
            .limit(batch_size)
            .all()
        )

        for bookmark in bookmarks:
            try:
                word = bookmark.user_word.meaning.origin.content
                context = bookmark.get_context()

                # Normalize for fair comparison
                word_norm = unicodedata.normalize('NFC', word).lower()
                context_norm = unicodedata.normalize('NFC', context).lower()

                if word_norm not in context_norm:
                    problematic_ids.append(bookmark.id)
            except Exception as e:
                # Skip bookmarks with errors
                pass

            checked += 1

        if checked % 1000 == 0 or checked == end_offset - start_offset:
            progress = start_percent + (checked / (end_offset - start_offset)) * (end_percent - start_percent)
            print(f'Progress: {checked}/{end_offset - start_offset} ({progress:.1f}%) - Found {len(problematic_ids)} problematic')

        if len(bookmarks) < batch_size:
            break

    print()
    print(f'Scan complete: Found {len(problematic_ids)} problematic bookmarks out of {checked} checked')
    return problematic_ids


def delete_bookmarks(bookmark_ids, dry_run=True):
    """
    Delete the problematic bookmarks and handle UserWord references properly.

    This follows the same logic as the delete_bookmark endpoint in
    zeeguu/api/endpoints/bookmarks_and_words.py
    """
    from zeeguu.core.model.user_word import UserWord
    from zeeguu.core.bookmark_quality.fit_for_study import fit_for_study

    if len(bookmark_ids) == 0:
        print('No bookmarks to delete')
        return

    if dry_run:
        print()
        print('=' * 80)
        print('DRY RUN MODE - No bookmarks will be deleted')
        print('=' * 80)
        print(f'Would delete {len(bookmark_ids)} bookmarks')
        print()
        print('First 10 bookmark IDs that would be deleted:')
        for bid in bookmark_ids[:10]:
            print(f'  - {bid}')
        if len(bookmark_ids) > 10:
            print(f'  ... and {len(bookmark_ids) - 10} more')
        print()
        print('To actually delete these bookmarks, run with: --delete')
        return

    print()
    print(f'Deleting {len(bookmark_ids)} bookmarks and handling UserWord references...')
    print()

    deleted = 0
    userwords_updated = 0

    # Process one at a time to properly handle UserWord relationships
    for bookmark_id in bookmark_ids:
        try:
            bookmark = db.session.get(Bookmark, bookmark_id)
            if not bookmark:
                continue

            user_word = bookmark.user_word

            # Delete any example_sentence_context records that reference this bookmark
            # This prevents foreign key constraint errors
            from sqlalchemy import text
            db.session.execute(
                text("DELETE FROM example_sentence_context WHERE bookmark_id = :bid"),
                {"bid": bookmark.id}
            )

            # Find all other bookmarks for this user_word
            other_bookmarks = (
                Bookmark.query.filter(Bookmark.user_word_id == user_word.id)
                .filter(Bookmark.id != bookmark.id)
                .all()
            )

            # Clear the preferred bookmark reference if it points to the bookmark we're deleting
            if user_word.preferred_bookmark_id == bookmark.id:
                user_word.preferred_bookmark = None
                db.session.add(user_word)
                db.session.flush()  # Ensure foreign key is cleared before deletion

                # If there are other bookmarks, try to find a new preferred one
                if other_bookmarks:
                    quality_bookmarks = [
                        b for b in other_bookmarks
                        if fit_for_study(b.user_word)
                    ]

                    if quality_bookmarks:
                        # Set the most recent quality bookmark as preferred
                        new_preferred = max(quality_bookmarks, key=lambda b: b.time)
                        user_word.preferred_bookmark = new_preferred
                        db.session.add(user_word)
                    else:
                        # No quality bookmarks left - just clear the schedule
                        # (Don't mark as unfit_for_study since other bookmarks exist)
                        from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
                        BasicSRSchedule.clear_user_word_schedule(db.session, user_word)
                        userwords_updated += 1
                else:
                    # No other bookmarks exist - mark as unfit for study AND clear schedule
                    # (Keep UserWord for historical data)
                    user_word.set_unfit_for_study(db.session)
                    userwords_updated += 1

            # Delete the bookmark
            db.session.delete(bookmark)
            deleted += 1

            # Commit in batches for performance
            if deleted % 100 == 0:
                db.session.commit()
                print(f'  Deleted {deleted}/{len(bookmark_ids)} bookmarks, updated {userwords_updated} UserWords...')

        except Exception as e:
            print(f'  ERROR processing bookmark {bookmark_id}: {e}')
            db.session.rollback()
            continue

    # Final commit
    db.session.commit()

    print()
    print(f'✓ Successfully deleted {deleted} problematic bookmarks')
    print(f'✓ Updated {userwords_updated} UserWords (marked as unfit for study)')
    print()
    print('NOTE: UserWords are preserved for historical data.')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Delete bookmarks where word does not appear in context')
    parser.add_argument('--delete', action='store_true', help='Actually delete the bookmarks (default is dry run)')
    parser.add_argument('--start', type=int, default=95, help='Start scanning from this percentage (0-100)')
    parser.add_argument('--end', type=int, default=100, help='Stop scanning at this percentage (0-100)')

    args = parser.parse_args()

    # Find problematic bookmarks
    problematic_ids = find_problematic_bookmarks(start_percent=args.start, end_percent=args.end)

    # Delete (or show what would be deleted)
    delete_bookmarks(problematic_ids, dry_run=not args.delete)
