#!/usr/bin/env python
"""
Prune old, unreferenced articles based on their feed's retention_class.

See zeeguu/docs/future-work/article-retention-perennial-vs-ephemeral.md
for the strategy.

Retention windows (days):
  ephemeral  →  180  (6 months)
  unknown    →  540  (18 months)
  perennial  →  None (don't age-prune; only deleted via the existing
                      anonymize_users.py unreferenced sweep)

Articles with no feed_id are treated as 'unknown'.
Articles are only deleted if BOTH:
  - older than the retention window for their class, AND
  - not referenced from user_article / text / user_reading_session /
    user_activity_data (same reference-set as anonymize_users.py)

Usage:
  python prune_old_articles.py             # dry-run (default)
  python prune_old_articles.py --apply     # actually delete

Run nightly via cron once the dry-run output looks right.
"""

import os
os.environ["PRELOAD_STANZA"] = "false"

import sys
import time
from datetime import datetime, timedelta

import zeeguu.core
from sqlalchemy import text
from zeeguu.api.app import create_app_for_scripts

RETENTION_DAYS = {
    "ephemeral": 180,
    "unknown": 540,
    "perennial": None,
}

BATCH_SIZE = 1000

apply_mode = "--apply" in sys.argv

app = create_app_for_scripts()
app.app_context().push()
db_session = zeeguu.core.model.db.session


def referenced_article_ids():
    """Articles referenced from anywhere — never safe to delete."""
    print("Building reference set...")
    ref = set()
    for tbl, col in [
        ("user_article", "article_id"),
        ("text", "article_id"),
        ("user_reading_session", "article_id"),
    ]:
        rows = db_session.execute(
            text(f"SELECT DISTINCT {col} FROM {tbl} WHERE {col} IS NOT NULL")
        )
        n_before = len(ref)
        ref.update(r[0] for r in rows)
        print(f"  {tbl}: +{len(ref) - n_before} (total {len(ref)})")

    # user_activity_data goes via source_id → article.source_id
    print("  user_activity_data via source_id...")
    source_ids = set(
        r[0]
        for r in db_session.execute(
            text(
                "SELECT DISTINCT source_id FROM user_activity_data "
                "WHERE source_id IS NOT NULL"
            )
        )
    )
    if source_ids:
        placeholders = ",".join(str(s) for s in source_ids)
        rows = db_session.execute(
            text(
                f"SELECT id FROM article WHERE source_id IN ({placeholders})"
            )
        )
        n_before = len(ref)
        ref.update(r[0] for r in rows)
        print(f"    +{len(ref) - n_before} (total {len(ref)})")

    return ref


def candidates_for_class(retention_class, days, referenced):
    """Article ids older than the cutoff for this class and unreferenced."""
    if days is None:
        return []

    cutoff = datetime.utcnow() - timedelta(days=days)
    # An article inherits its class from feed.retention_class; articles with
    # no feed (or unknown class) fall under 'unknown'.
    if retention_class == "unknown":
        sql = text(
            """
            SELECT a.id
            FROM article a
            LEFT JOIN feed f ON f.id = a.feed_id
            WHERE a.published_time < :cutoff
              AND (a.feed_id IS NULL OR f.retention_class = 'unknown')
            """
        )
    else:
        sql = text(
            """
            SELECT a.id
            FROM article a
            JOIN feed f ON f.id = a.feed_id
            WHERE a.published_time < :cutoff
              AND f.retention_class = :rc
            """
        )

    print(f"  querying {retention_class} articles older than {cutoff:%Y-%m-%d}...")
    rows = db_session.execute(sql, {"cutoff": cutoff, "rc": retention_class})
    candidate_ids = [r[0] for r in rows]
    print(f"    age-filter matched {len(candidate_ids)}")

    unreferenced = [aid for aid in candidate_ids if aid not in referenced]
    print(
        f"    of those, unreferenced (will delete): {len(unreferenced)} "
        f"(referenced+kept: {len(candidate_ids) - len(unreferenced)})"
    )
    return unreferenced


def delete_in_batches(ids):
    """Bulk-delete with FK checks off (rows are unreferenced — verified)."""
    db_session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    db_session.commit()

    total = len(ids)
    deleted = 0
    t0 = time.time()
    try:
        for i in range(0, total, BATCH_SIZE):
            batch = ids[i : i + BATCH_SIZE]
            placeholders = ",".join(str(x) for x in batch)
            db_session.execute(
                text(f"DELETE FROM article WHERE id IN ({placeholders})")
            )
            db_session.commit()
            deleted += len(batch)
            if deleted % 10000 == 0 or deleted == total:
                pct = 100 * deleted // total if total else 100
                print(f"    deleted {deleted}/{total} ({pct}%)")
    finally:
        db_session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        db_session.commit()

    print(f"  done in {time.time() - t0:.1f}s")


def main():
    print(f"=== prune_old_articles ({'APPLY' if apply_mode else 'DRY-RUN'}) ===")

    referenced = referenced_article_ids()

    summary = {}
    to_delete_all = []

    for rc, days in RETENTION_DAYS.items():
        if days is None:
            print(f"\n{rc}: skipped (no age-based pruning)")
            summary[rc] = 0
            continue
        print(f"\n{rc}: retention = {days} days")
        ids = candidates_for_class(rc, days, referenced)
        summary[rc] = len(ids)
        to_delete_all.extend(ids)

    print(f"\n=== Summary ===")
    for rc, n in summary.items():
        print(f"  {rc}: {n}")
    print(f"  total to delete: {len(to_delete_all)}")

    if not apply_mode:
        print("\nDry-run only. Re-run with --apply to actually delete.")
        return

    if not to_delete_all:
        return

    print(f"\nDeleting {len(to_delete_all)} articles...")
    delete_in_batches(to_delete_all)
    print("Done.")


if __name__ == "__main__":
    main()
