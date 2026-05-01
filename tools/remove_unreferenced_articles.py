#!/usr/bin/env python
"""
Remove unreferenced articles and all their dependent data.

This script:
1. Finds articles not referenced by users (no user_article, text, user_reading_session, etc.)
2. Deletes dependent data FIRST (article_fragment, tokenization_cache, etc.)
3. Deletes the articles
4. Cleans up orphaned source, source_text, and new_text records

Usage:
    python remove_unreferenced_articles.py [--days N] [--delete-from-es]

Options:
    --days N         Only delete articles older than N days (default: all unreferenced)
    --delete-from-es Also remove from Elasticsearch index
"""
import os
os.environ["PRELOAD_STANZA"] = "false"

import argparse
from sqlalchemy import text

from zeeguu.api.app import create_app
from zeeguu.core.model.db import db

app = create_app()
app.app_context().push()
dbs = db.session


def find_unreferenced_article_ids(days=None):
    """Find article IDs that are not referenced by any user data."""
    print("Building set of referenced article IDs...")

    # Get referenced article IDs from each table
    print("  - checking user_article...")
    ref1 = set(row[0] for row in dbs.execute(
        text("SELECT DISTINCT article_id FROM user_article WHERE article_id IS NOT NULL")))
    print(f"    {len(ref1)} articles")

    print("  - checking text...")
    ref2 = set(row[0] for row in dbs.execute(
        text("SELECT DISTINCT article_id FROM text WHERE article_id IS NOT NULL")))
    print(f"    {len(ref2)} articles")

    print("  - checking user_reading_session...")
    ref3 = set(row[0] for row in dbs.execute(
        text("SELECT DISTINCT article_id FROM user_reading_session WHERE article_id IS NOT NULL")))
    print(f"    {len(ref3)} articles")

    print("  - checking cohort_article_map...")
    ref4 = set(row[0] for row in dbs.execute(
        text("SELECT DISTINCT article_id FROM cohort_article_map WHERE article_id IS NOT NULL")))
    print(f"    {len(ref4)} articles")

    print("  - checking user_activity_data source_ids...")
    source_ids = set(row[0] for row in dbs.execute(
        text("SELECT DISTINCT source_id FROM user_activity_data WHERE source_id IS NOT NULL")))
    print(f"    {len(source_ids)} source_ids")

    referenced_article_ids = ref1 | ref2 | ref3 | ref4
    print(f"Total referenced articles: {len(referenced_article_ids)}")

    # Get all article IDs
    print("Getting all article IDs...")
    if days:
        all_articles = list(dbs.execute(text(f"""
            SELECT id, source_id FROM article
            WHERE published_time < DATE_SUB(NOW(), INTERVAL {days} DAY)
        """)))
    else:
        all_articles = list(dbs.execute(text("SELECT id, source_id FROM article")))
    print(f"Total articles to check: {len(all_articles)}")

    # Find unreferenced
    unreferenced = [
        row[0] for row in all_articles
        if row[0] not in referenced_article_ids and row[1] not in source_ids
    ]
    print(f"Found {len(unreferenced)} unreferenced articles to delete")

    return unreferenced


def delete_from_dependent_tables(article_ids, batch_size=1000):
    """Delete from all tables that reference article before deleting articles."""
    if not article_ids:
        return

    dependent_tables = [
        "article_tokenization_cache",
        "article_cefr_assessment",
        "article_classification",
        "article_topic_map",
        "article_url_keyword_map",
        "article_broken_code_map",
        "article_difficulty_feedback",
        "article_summary_context",
        "article_title_context",
        "grammar_correction_log",
        "article_fragment",
    ]

    total = len(article_ids)
    for table in dependent_tables:
        print(f"Deleting from {table}...")
        deleted_from_table = 0
        for i in range(0, total, batch_size):
            batch = article_ids[i:i + batch_size]
            placeholders = ",".join(str(id) for id in batch)
            try:
                result = dbs.execute(text(f"DELETE FROM {table} WHERE article_id IN ({placeholders})"))
                dbs.commit()
                deleted_from_table += result.rowcount
            except Exception as e:
                dbs.rollback()
                # Table might not exist or have different schema
                print(f"  Warning: {e}")
                break
        if deleted_from_table > 0:
            print(f"  Deleted {deleted_from_table} rows")


def delete_articles(article_ids, delete_from_es=False, batch_size=1000):
    """Delete the articles themselves."""
    if not article_ids:
        return 0

    total = len(article_ids)
    deleted = 0

    if delete_from_es:
        from zeeguu.core.model import Article
        from zeeguu.core.elastic.indexing import remove_from_index

    print("Deleting articles...")
    for i in range(0, total, batch_size):
        batch = article_ids[i:i + batch_size]
        placeholders = ",".join(str(id) for id in batch)

        if delete_from_es:
            for aid in batch:
                article = Article.find_by_id(aid)
                if article:
                    remove_from_index(article)

        try:
            dbs.execute(text(f"DELETE FROM article WHERE id IN ({placeholders})"))
            dbs.commit()
            deleted += len(batch)
            if deleted % 10000 == 0 or deleted == total:
                print(f"  Deleted {deleted}/{total} articles ({100*deleted//total}%)")
        except Exception as e:
            print(f"Error deleting batch: {e}")
            dbs.rollback()

    return deleted


def cleanup_orphaned_sources(batch_size=50000):
    """Clean up source records not referenced by anything."""
    print("Cleaning up orphaned source records...")
    deleted = 0
    while True:
        result = dbs.execute(text("""
            DELETE FROM source WHERE id IN (
                SELECT s.id FROM (
                    SELECT source.id FROM source
                    LEFT JOIN article ON source.id = article.source_id
                    LEFT JOIN bookmark ON source.id = bookmark.source_id
                    LEFT JOIN user_activity_data ON source.id = user_activity_data.source_id
                    LEFT JOIN video ON source.id = video.source_id
                    WHERE article.id IS NULL AND bookmark.id IS NULL
                      AND user_activity_data.id IS NULL AND video.id IS NULL
                    LIMIT %d
                ) s
            )
        """ % batch_size))
        dbs.commit()
        if result.rowcount == 0:
            break
        deleted += result.rowcount
        if deleted % 100000 == 0:
            print(f"  Deleted {deleted} orphaned sources...")
    print(f"  Total deleted: {deleted}")
    return deleted


def cleanup_orphaned_source_text(batch_size=50000):
    """Clean up source_text records not referenced by any source."""
    print("Cleaning up orphaned source_text records...")
    deleted = 0
    while True:
        result = dbs.execute(text("""
            DELETE FROM source_text WHERE id IN (
                SELECT s.id FROM (
                    SELECT source_text.id FROM source_text
                    LEFT JOIN source ON source_text.id = source.source_text_id
                    WHERE source.id IS NULL
                    LIMIT %d
                ) s
            )
        """ % batch_size))
        dbs.commit()
        if result.rowcount == 0:
            break
        deleted += result.rowcount
        if deleted % 100000 == 0:
            print(f"  Deleted {deleted} orphaned source_text...")
    print(f"  Total deleted: {deleted}")
    return deleted


def cleanup_orphaned_new_text(batch_size=50000):
    """Clean up new_text records not referenced by any article_fragment."""
    print("Cleaning up orphaned new_text records...")
    deleted = 0
    while True:
        result = dbs.execute(text("""
            DELETE FROM new_text WHERE id IN (
                SELECT s.id FROM (
                    SELECT new_text.id FROM new_text
                    LEFT JOIN article_fragment ON new_text.id = article_fragment.text_id
                    WHERE article_fragment.id IS NULL
                    LIMIT %d
                ) s
            )
        """ % batch_size))
        dbs.commit()
        if result.rowcount == 0:
            break
        deleted += result.rowcount
        if deleted % 500000 == 0:
            print(f"  Deleted {deleted} orphaned new_text...")
    print(f"  Total deleted: {deleted}")
    return deleted


def main():
    parser = argparse.ArgumentParser(description="Remove unreferenced articles and their dependents")
    parser.add_argument("--days", type=int, help="Only delete articles older than N days")
    parser.add_argument("--delete-from-es", action="store_true", help="Also remove from Elasticsearch")
    args = parser.parse_args()

    # Find unreferenced articles
    unreferenced_ids = find_unreferenced_article_ids(days=args.days)

    if not unreferenced_ids:
        print("No unreferenced articles found.")
        return

    # Delete dependents first
    delete_from_dependent_tables(unreferenced_ids)

    # Delete articles
    deleted = delete_articles(unreferenced_ids, delete_from_es=args.delete_from_es)
    print(f"Deleted {deleted} articles")

    # Clean up orphaned content tables
    cleanup_orphaned_sources()
    cleanup_orphaned_source_text()
    cleanup_orphaned_new_text()

    print("\nArticle cleanup complete!")


if __name__ == "__main__":
    main()
