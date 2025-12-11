#!/usr/bin/env python
"""
Migration script to backfill reading_session_id on existing bookmarks.

For each bookmark without a reading_session_id, finds the reading session where:
- Same user
- Same article
- Bookmark creation time falls within the reading session's time window

Run with: source ~/.venvs/z_env/bin/activate && python tools/migrations/25-12-11--backfill_reading_session_id_on_bookmarks.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.user_reading_session import UserReadingSession
from datetime import timedelta


def backfill_reading_session_ids(dry_run=True, batch_size=1000):
    """
    Backfill reading_session_id for bookmarks that don't have one.

    Args:
        dry_run: If True, don't commit changes, just show what would be done
        batch_size: Number of bookmarks to process before committing
    """

    # Find bookmarks without reading_session_id that have a text (from reading)
    bookmarks_to_update = (
        Bookmark.query
        .filter(Bookmark.reading_session_id == None)
        .filter(Bookmark.text_id != None)
        .all()
    )

    print(f"Found {len(bookmarks_to_update)} bookmarks without reading_session_id")

    updated_count = 0
    no_session_count = 0
    no_article_count = 0

    for i, bookmark in enumerate(bookmarks_to_update):
        if i % 1000 == 0 and i > 0:
            print(f"Processed {i} bookmarks...")
            if not dry_run:
                db.session.commit()

        # Get user_id and article_id
        if not bookmark.user_word:
            no_article_count += 1
            continue

        user_id = bookmark.user_word.user_id

        if not bookmark.text or not bookmark.text.article_id:
            no_article_count += 1
            continue

        article_id = bookmark.text.article_id
        bookmark_time = bookmark.time

        # Find matching reading session
        # A bookmark belongs to a session if its time is between start_time and last_action_time
        matching_session = (
            UserReadingSession.query
            .filter(UserReadingSession.user_id == user_id)
            .filter(UserReadingSession.article_id == article_id)
            .filter(UserReadingSession.start_time <= bookmark_time)
            .filter(UserReadingSession.last_action_time >= bookmark_time)
            .first()
        )

        if matching_session:
            if not dry_run:
                bookmark.reading_session_id = matching_session.id
            updated_count += 1
        else:
            no_session_count += 1

    if not dry_run:
        db.session.commit()

    print(f"\n{'DRY RUN - ' if dry_run else ''}Results:")
    print(f"  Bookmarks updated: {updated_count}")
    print(f"  Bookmarks with no matching session: {no_session_count}")
    print(f"  Bookmarks with no article: {no_article_count}")

    return updated_count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill reading_session_id on bookmarks")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry run)")
    args = parser.parse_args()

    dry_run = not args.apply

    if dry_run:
        print("Running in DRY RUN mode. Use --apply to actually update the database.\n")
    else:
        print("Running in APPLY mode. Changes will be committed to the database.\n")

    backfill_reading_session_ids(dry_run=dry_run)
