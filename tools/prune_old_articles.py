#!/usr/bin/env python
"""
Prune old, unreferenced articles based on their feed's retention_class.

See zeeguu/docs/future-work/article-retention-perennial-vs-ephemeral.md
for the strategy.

Retention windows (days):
  ephemeral  →  per feed: roughly its last 100 articles, between 90 and 540
                days; 180 while its pace is unmeasured
                (zeeguu/core/feed_cadence.py)
  unknown    →  540  (18 months)
  perennial  →  None (don't age-prune; only deleted via the existing
                      anonymize_users.py unreferenced sweep)

Also deletes skipped_url rows older than SKIPPED_URL_RETENTION_DAYS: by then
the feed items they stand for have left the feeds.

Articles with no feed_id are treated as 'unknown'. An article is deleted if it
is older than its class's retention window AND not in the reference pre-filter.

Deletion is done by zeeguu.core.article_pruning.delete_articles_in_batches with
FK checks ON: the DB cascades each article's owned children (fragments,
tokenization, simplified children, ...), referenced articles are protected, and
the shared content (new_text/source/source_text) is reclaimed inline. Requires
migration 26-05-26--restrict-article-fk-for-prune-protection.sql.

Usage:
  python prune_old_articles.py                       # dry-run (default)
  python prune_old_articles.py --apply               # actually delete
  python prune_old_articles.py --apply --skip-binlog # big one-off purge, no-replica box:
                                                     # skip binlog writes (big I/O win;
                                                     # needs SUPER on the DB user)

Run nightly via cron once the dry-run output looks right.
"""

import sys
from datetime import datetime, timedelta

import zeeguu.core
from sqlalchemy import text
from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.feed_cadence import EPHEMERAL_DEFAULT_DAYS, ephemeral_retention_days
from zeeguu.core.model.skipped_url import SkippedUrl
from zeeguu.core.article_pruning import (
    referenced_article_ids,
    delete_articles_in_batches,
)

# Ephemeral feeds get a window per feed instead; see ephemeral_candidates.
RETENTION_DAYS = {
    "unknown": 540,
    "perennial": None,
}

SKIPPED_URL_RETENTION_DAYS = 30

apply_mode = "--apply" in sys.argv
skip_binlog = "--skip-binlog" in sys.argv  # big one-off purge on a no-replica box only

app = create_app_for_scripts()
app.app_context().push()
db_session = zeeguu.core.model.db.session


def candidates_for_class(retention_class, days, referenced):
    """Article ids older than the cutoff for this class and not referenced."""
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
    candidate_ids = [r[0] for r in db_session.execute(sql, {"cutoff": cutoff, "rc": retention_class})]
    print(f"    age-filter matched {len(candidate_ids)}")

    unreferenced = [aid for aid in candidate_ids if aid not in referenced]
    print(
        f"    of those, unreferenced (will delete): {len(unreferenced)} "
        f"(referenced+kept: {len(candidate_ids) - len(unreferenced)})"
    )
    return unreferenced


def ephemeral_candidates(referenced):
    """Like candidates_for_class, but each ephemeral feed gets a window scaled
    by how often it publishes: a fast news feed keeps less time, a slow blog
    more."""
    feeds = db_session.execute(
        text(
            """
            SELECT id, title, typical_gap_hours
            FROM feed
            WHERE retention_class = 'ephemeral'
            """
        )
    ).fetchall()

    unreferenced = []
    for feed_id, title, gap_hours in feeds:
        days = ephemeral_retention_days(gap_hours)
        cutoff = datetime.utcnow() - timedelta(days=days)
        candidate_ids = [
            r[0]
            for r in db_session.execute(
                text(
                    """
                    SELECT id FROM article
                    WHERE feed_id = :feed_id AND published_time < :cutoff
                    """
                ),
                {"feed_id": feed_id, "cutoff": cutoff},
            )
        ]
        ids = [aid for aid in candidate_ids if aid not in referenced]
        if days != EPHEMERAL_DEFAULT_DAYS or ids:
            print(
                f"    {title} (id={feed_id}): {days}d (was {EPHEMERAL_DEFAULT_DAYS}d)"
                f" — will delete {len(ids)}"
            )
        unreferenced.extend(ids)

    print(f"    ephemeral total, unreferenced (will delete): {len(unreferenced)}")
    return unreferenced


def prune_skipped_urls():
    cutoff = datetime.utcnow() - timedelta(days=SKIPPED_URL_RETENTION_DAYS)
    old = SkippedUrl.skipped_before(cutoff)
    print(f"\nskipped_url: {old.count()} rows older than {cutoff:%Y-%m-%d}")
    if apply_mode:
        old.delete(synchronize_session=False)
        db_session.commit()


def main():
    print(f"=== prune_old_articles ({'APPLY' if apply_mode else 'DRY-RUN'}) ===")

    prune_skipped_urls()

    referenced = referenced_article_ids(db_session)

    print("\nephemeral: retention per feed")
    to_delete_all = ephemeral_candidates(referenced)
    summary = {"ephemeral": len(to_delete_all)}
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

    print(f"\nDeleting {len(to_delete_all)} articles{' (binlog off)' if skip_binlog else ''}...")
    delete_articles_in_batches(db_session, to_delete_all, skip_binlog=skip_binlog)
    print("Done.")


if __name__ == "__main__":
    main()
