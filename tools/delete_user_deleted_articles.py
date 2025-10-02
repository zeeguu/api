#!/usr/bin/env python
"""
Script to permanently delete articles that are marked as deleted (deleted=1)
for a specific user.

Usage:
    source ~/.venvs/z_env/bin/activate && python -m tools.delete_user_deleted_articles <user_id> [--confirm]

Example:
    source ~/.venvs/z_env/bin/activate && python -m tools.delete_user_deleted_articles 5221 --confirm
"""

import sys
from zeeguu.api.app import create_app
from zeeguu.core.model import Article, User
from zeeguu.core.model.db import db

app = create_app()
app.app_context().push()

dbs = db.session


def delete_deleted_articles_for_user(user_id, confirm=False):
    """
    Find and permanently delete all articles that:
    1. Are marked as deleted (deleted=1)
    2. Were uploaded by the specified user (uploader_id)
    """

    user = User.find_by_id(user_id)
    if not user:
        print(f"User {user_id} not found!")
        return

    print(f"Finding deleted articles for user: {user.name} (ID: {user_id})")

    # Find all articles uploaded by this user that are marked as deleted
    deleted_articles = Article.query.filter_by(
        uploader_id=user_id,
        deleted=1
    ).all()

    print(f"Found {len(deleted_articles)} deleted articles")

    if not deleted_articles:
        print("No deleted articles to remove.")
        return

    # Show what we're about to delete
    print("\nArticles to be permanently deleted:")
    for article in deleted_articles:
        print(f"  - ID: {article.id}, Title: {article.title[:60]}...")

    if not confirm:
        print("\nRun with --confirm to actually delete these articles")
        return

    # Delete the articles
    deleted_count = 0
    skipped_count = 0
    for article in deleted_articles:
        try:
            # Use the Article.safe_delete method which handles all the logic
            was_permanently_deleted = article.safe_delete(dbs, user)

            if was_permanently_deleted:
                deleted_count += 1
                print(f"Deleted article ID: {article.id}")
            else:
                skipped_count += 1
                print(f"Skipping article ID: {article.id} - other users have interacted with it")

        except Exception as e:
            print(f"Error deleting article {article.id}: {e}")
            import traceback
            traceback.print_exc()
            dbs.rollback()
            continue

    print(f"\nSuccessfully deleted {deleted_count} articles.")
    print(f"Skipped {skipped_count} articles (other users have interacted with them).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m tools.delete_user_deleted_articles <user_id> [--confirm]")
        print("Example: python -m tools.delete_user_deleted_articles 5221 --confirm")
        sys.exit(1)

    try:
        user_id = int(sys.argv[1])
        confirm = "--confirm" in sys.argv
        delete_deleted_articles_for_user(user_id, confirm)
    except ValueError:
        print("Error: user_id must be a number")
        sys.exit(1)
