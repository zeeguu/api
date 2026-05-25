#!/usr/bin/env python
"""
Purge orphaned article content left behind by article deletion.

Background
----------
`remove_unreferenced_articles.py` deletes articles via `db.session.delete(article)`.
The Article ORM cascades only to `article_fragment`, `article_tokenization_cache`
and `cefr_assessment`. It does NOT cascade to the content tables those rows point
at -- `new_text`, `source`, `source_text` -- so every deletion run leaks them.
Combined with a historical backlog (deletions that predate the cascades), this can
leave 95%+ of the content tables orphaned.

This tool removes content rows that are no longer referenced by anything that
matters -- crucially, it preserves rows still referenced by USER DATA
(bookmarks, bookmark contexts, captions, reading activity, video), not just by
surviving articles.

Deletion order (matters, because of FK dependencies):
    1. article_fragment           -- orphaned (article gone). Cascades to
                                     article_fragment_context (verified: never
                                     tied to a surviving bookmark for orphans).
    2. article_tokenization_cache -- orphaned (article gone).
    3. new_text                   -- not referenced by any article_fragment
                                     (after step 1), bookmark_context, or caption.
    4. source                     -- not referenced by any article, bookmark,
                                     user_activity_data, or video.
    5. source_text                -- not referenced by any source (after step 4).

Safe to run repeatedly (idempotent). Dry-run by default.

Usage:
    python -m tools.cleanup_orphaned_content                # dry run: report only
    python -m tools.cleanup_orphaned_content --execute      # actually delete
    python -m tools.cleanup_orphaned_content --execute --optimize   # + reclaim disk
    python -m tools.cleanup_orphaned_content --execute --batch-size 20000
"""
import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()


# Each step: a table and the WHERE predicate identifying rows safe to delete.
# The predicate must reference the table by name (used in both COUNT and DELETE).
STEPS = [
    {
        "name": "article_fragment (article deleted)",
        "table": "article_fragment",
        "where": (
            "NOT EXISTS (SELECT 1 FROM article a "
            "WHERE a.id = article_fragment.article_id)"
        ),
    },
    {
        "name": "article_tokenization_cache (article deleted)",
        "table": "article_tokenization_cache",
        "where": (
            "NOT EXISTS (SELECT 1 FROM article a "
            "WHERE a.id = article_tokenization_cache.article_id)"
        ),
    },
    {
        # Kept if referenced by a fragment of a SURVIVING article, a bookmark
        # context, or a caption. The join to `article` (rather than plain
        # fragment existence) makes the count order-independent: it reports the
        # true deletable total even before step 1 has removed orphaned fragments.
        "name": "new_text (no live fragment / bookmark_context / caption)",
        "table": "new_text",
        "where": (
            "NOT EXISTS (SELECT 1 FROM article_fragment f JOIN article a ON f.article_id = a.id "
            "            WHERE f.text_id = new_text.id) "
            "AND NOT EXISTS (SELECT 1 FROM bookmark_context bc WHERE bc.text_id = new_text.id) "
            "AND NOT EXISTS (SELECT 1 FROM caption c WHERE c.text_id = new_text.id)"
        ),
    },
    {
        "name": "source (no article / bookmark / activity / video)",
        "table": "source",
        "where": (
            "NOT EXISTS (SELECT 1 FROM article a WHERE a.source_id = source.id) "
            "AND NOT EXISTS (SELECT 1 FROM bookmark b WHERE b.source_id = source.id) "
            "AND NOT EXISTS (SELECT 1 FROM user_activity_data u WHERE u.source_id = source.id) "
            "AND NOT EXISTS (SELECT 1 FROM video v WHERE v.source_id = source.id)"
        ),
    },
    {
        # Kept if referenced by a source that itself survives (i.e. a source
        # still referenced by an article, bookmark, activity row, or video).
        # The nested alive-check keeps the count order-independent vs step 4.
        "name": "source_text (no live source)",
        "table": "source_text",
        "where": (
            "NOT EXISTS (SELECT 1 FROM source s WHERE s.source_text_id = source_text.id AND ("
            "    EXISTS (SELECT 1 FROM article a WHERE a.source_id = s.id) "
            " OR EXISTS (SELECT 1 FROM bookmark b WHERE b.source_id = s.id) "
            " OR EXISTS (SELECT 1 FROM user_activity_data u WHERE u.source_id = s.id) "
            " OR EXISTS (SELECT 1 FROM video v WHERE v.source_id = s.id)))"
        ),
    },
]


def count_deletable(step):
    sql = f"SELECT COUNT(*) FROM {step['table']} WHERE {step['where']}"
    return db.session.execute(text(sql)).scalar()


def delete_batched(step, batch_size):
    sql = text(f"DELETE FROM {step['table']} WHERE {step['where']} LIMIT :n")
    total = 0
    while True:
        result = db.session.execute(sql, {"n": batch_size})
        db.session.commit()
        n = result.rowcount
        total += n
        if n:
            print(f"      ... deleted {total:,} from {step['table']}", flush=True)
        if n < batch_size:
            break
    return total


def optimize(step):
    print(f"      OPTIMIZE TABLE {step['table']} (reclaiming disk)...", flush=True)
    db.session.execute(text(f"OPTIMIZE TABLE {step['table']}"))
    db.session.commit()


def main():
    parser = argparse.ArgumentParser(description="Purge orphaned article content")
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually delete. Without this flag, only reports what would be deleted.",
    )
    parser.add_argument(
        "--optimize", action="store_true",
        help="Run OPTIMIZE TABLE after deleting to return freed space to the OS.",
    )
    parser.add_argument(
        "--batch-size", type=int, default=50000,
        help="Rows to delete per transaction (default: 50000).",
    )
    args = parser.parse_args()

    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(f"=== cleanup_orphaned_content [{mode}] ===\n")

    start = time.time()
    grand_total = 0
    for step in STEPS:
        print(f">>> {step['name']}")
        n = count_deletable(step)
        print(f"    deletable rows: {n:,}")
        if args.execute and n:
            deleted = delete_batched(step, args.batch_size)
            print(f"    DELETED {deleted:,}")
            if args.optimize:
                optimize(step)
        grand_total += n
        print()

    verb = "Deleted" if args.execute else "Would delete"
    print(f"=== {verb} {grand_total:,} rows in {int(time.time() - start)}s ===")
    if not args.execute:
        print("Re-run with --execute to apply (and --optimize to reclaim disk).")


if __name__ == "__main__":
    main()
