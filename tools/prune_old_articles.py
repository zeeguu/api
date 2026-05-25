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

# Derived/computed children of `article` to delete when pruning it. The bulk
# delete below runs with FOREIGN_KEY_CHECKS=0 (needed to get past article's
# NO ACTION children such as user_article / user_reading_session), which also
# suppresses real ON DELETE CASCADE — that's what was leaving these regenerable
# tables full of orphans.
#
# This is DELIBERATELY a subset of article's cascade children: it lists only
# computed/cache data that is meaningless once the article is gone. We
# intentionally do NOT delete the user/research/teacher cascade children
# (user_activity_data, personal_copy, cohort_article_map,
# article_topic_user_feedback, user_article_broken_report) — that data is worth
# preserving even after an article is pruned. So do NOT "re-sync" this list to
# the full DELETE_RULE='CASCADE' set; the omissions are on purpose.
# (article_fragment is handled separately so its own cascade child,
#  article_fragment_context, is cleaned first.)
CASCADE_CHILDREN = [
    "article_broken_code_map",
    "article_cefr_assessment",
    "article_classification",
    "article_tokenization_cache",
    "article_topic_map",
    "article_url_keyword_map",
    "difficulty_lingo_rank",
    "grammar_correction_log",
]

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


def delete_article_owned_children(placeholders):
    """Delete an article batch's derived/computed children explicitly.

    FOREIGN_KEY_CHECKS=0 suppresses real cascades, so we clean these here to
    avoid leaving orphaned fragments/tokenization/etc. Scope is deliberately
    narrow (see CASCADE_CHILDREN): only regenerable data. It does NOT touch
    user/research cascade children (user_activity_data, personal_copy,
    cohort_article_map, ...) — those are preserved — nor the shared,
    deduplicated content tables (new_text / source / source_text), which can be
    shared across articles/user data and are reclaimed separately by
    tools/cleanup_orphaned_content.py.
    """
    # article_fragment_context hangs off article_fragment (cascade); delete it
    # first, while the fragments still exist to identify it.
    db_session.execute(
        text(
            "DELETE FROM article_fragment_context "
            "WHERE article_fragment_id IN "
            f"(SELECT id FROM article_fragment WHERE article_id IN ({placeholders}))"
        )
    )
    db_session.execute(
        text(f"DELETE FROM article_fragment WHERE article_id IN ({placeholders})")
    )
    for child in CASCADE_CHILDREN:
        db_session.execute(
            text(f"DELETE FROM {child} WHERE article_id IN ({placeholders})")
        )


def delete_in_batches(ids):
    """Bulk-delete unreferenced articles and their owned children.

    Runs with FK checks off (to get past article's NO ACTION children, which the
    caller has already verified are unreferenced) and deletes each article's
    cascade-owned children explicitly, since FK-checks-off suppresses cascades.
    """
    db_session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    db_session.commit()

    total = len(ids)
    deleted = 0
    t0 = time.time()
    try:
        for i in range(0, total, BATCH_SIZE):
            batch = ids[i : i + BATCH_SIZE]
            placeholders = ",".join(str(x) for x in batch)
            delete_article_owned_children(placeholders)
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
    print(
        "  note: shared content (new_text/source/source_text) is reclaimed "
        "separately by tools/cleanup_orphaned_content.py"
    )


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
