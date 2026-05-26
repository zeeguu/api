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

Articles with no feed_id are treated as 'unknown'. An article is deleted if it
is older than its class's retention window AND not in the reference pre-filter
(referenced_article_ids).

Deletion runs with FK checks ON — the database enforces correctness:
  - derived children (article_fragment, *_tokenization_cache, cefr,
    classification, topic/url-keyword/difficulty maps, grammar_log) and
    simplified children (parent_article_id) are ON DELETE CASCADE → the DB
    deletes them automatically.
  - data we keep (personal_copy, user_activity_data, cohort_article_map,
    article_topic_user_feedback, user_article_broken_report) plus bookmark /
    reading tables BLOCK the delete (RESTRICT / NO ACTION). The pre-filter is
    supposed to have excluded every such article already.
  - shared, deduplicated content (new_text / source / source_text) has no FK
    from article, so prune reclaims it itself after each batch — but only the
    rows the batch touched that nobody else references (see
    reclaim_shared_content). tools/cleanup_orphaned_content.py stays for the
    one-time historical backlog and the anonymization pipeline.

If a delete is still blocked by a FK, the pre-filter is incomplete: we ABORT
LOUDLY (naming the constraint) rather than skip, so the missing table gets added
to referenced_article_ids() and we never force-delete referenced data.
(Requires migration 26-05-26--restrict-article-fk-for-prune-protection.sql.)

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
from sqlalchemy.exc import IntegrityError
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
        # Articles referenced by data we keep. Every table here has a
        # RESTRICT/NO ACTION FK on article_id, so the DB would block the delete
        # anyway — excluding them up front just avoids triggering that block.
        # This list should match the set of blocking FKs; if it drifts,
        # delete_in_batches aborts loudly rather than skipping, so the gap shows.
        #   - switched to RESTRICT by the 26-05-26 migration:
        ("personal_copy", "article_id"),
        ("cohort_article_map", "article_id"),
        ("user_activity_data", "article_id"),
        ("article_topic_user_feedback", "article_id"),
        ("user_article_broken_report", "article_id"),
        #   - already NO ACTION (bookmark summary/title context, feedback, MWE):
        ("article_summary_context", "article_id"),
        ("article_title_context", "article_id"),
        ("article_difficulty_feedback", "article_id"),
        ("topic_user_feedback", "article_id"),
        ("user_mwe_override", "article_id"),
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

    # Protect the ORIGINAL of any referenced simplification. parent_article_id
    # is ON DELETE CASCADE, so deleting an original would cascade to (and, if it
    # is referenced, be blocked by) its simplification. Keeping the original
    # whenever a simplification is referenced keeps the family together and
    # never orphans a simplification. (Simplifications don't nest, so one level.)
    if ref:
        print("  originals of referenced simplifications...")
        placeholders = ",".join(str(a) for a in ref)
        rows = db_session.execute(
            text(
                f"SELECT DISTINCT parent_article_id FROM article "
                f"WHERE id IN ({placeholders}) AND parent_article_id IS NOT NULL"
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


def _ids(sql):
    return [r[0] for r in db_session.execute(text(sql))]


def reclaim_shared_content(text_ids, source_ids, source_text_ids):
    """Delete the shared, de-duplicated content a just-pruned batch pointed at,
    but ONLY the rows now referenced by nobody.

    new_text / source / source_text have no FK from article and can be shared
    across articles or with bookmarks/captions, so the cascade can't touch them.
    We delete only within the ids the batch touched (targeted -> no full-table
    scan), guarded by NOT EXISTS so a row still used by a surviving article or a
    bookmark/caption is kept. Returns (n_new_text, n_source, n_source_text).
    """
    n_text = n_src = n_stext = 0
    if text_ids:
        ph = ",".join(str(t) for t in text_ids)
        n_text = db_session.execute(text(
            f"DELETE FROM new_text WHERE id IN ({ph}) "
            "AND NOT EXISTS (SELECT 1 FROM article_fragment f WHERE f.text_id = new_text.id) "
            "AND NOT EXISTS (SELECT 1 FROM bookmark_context bc WHERE bc.text_id = new_text.id) "
            "AND NOT EXISTS (SELECT 1 FROM caption c WHERE c.text_id = new_text.id)"
        )).rowcount
    if source_ids:
        ph = ",".join(str(s) for s in source_ids)
        n_src = db_session.execute(text(
            f"DELETE FROM source WHERE id IN ({ph}) "
            "AND NOT EXISTS (SELECT 1 FROM article a WHERE a.source_id = source.id) "
            "AND NOT EXISTS (SELECT 1 FROM bookmark b WHERE b.source_id = source.id) "
            "AND NOT EXISTS (SELECT 1 FROM user_activity_data u WHERE u.source_id = source.id) "
            "AND NOT EXISTS (SELECT 1 FROM video v WHERE v.source_id = source.id)"
        )).rowcount
    if source_text_ids:
        ph = ",".join(str(s) for s in source_text_ids)
        n_stext = db_session.execute(text(
            f"DELETE FROM source_text WHERE id IN ({ph}) "
            "AND NOT EXISTS (SELECT 1 FROM source s WHERE s.source_text_id = source_text.id)"
        )).rowcount
    return n_text, n_src, n_stext


def delete_in_batches(ids):
    """Delete articles in batches with FK checks ON, reclaiming shared content.

    The database cascades each article's OWNED children (fragments, tokenization
    cache, cefr/classification/topic maps, simplified children, ...) and BLOCKS
    the deletion of any article still referenced by a protected table
    (personal_copy, user_activity_data, bookmarks, reading sessions, ...).

    referenced_article_ids() is supposed to have already excluded every such
    article. If a delete is nevertheless blocked, the pre-filter is missing a
    table — we ABORT LOUDLY (re-raising, naming the FK) instead of skipping, so
    the omission is noticed and fixed. Batches already committed stay deleted;
    re-running after fixing the pre-filter simply continues.

    The shared, de-duplicated content tables (new_text / source / source_text)
    have no FK from article, so the cascade can't reach them. We reclaim them
    here, scoped to the ids each batch touched (see reclaim_shared_content) — so
    prune cleans up after itself without a full-table sweep. (The standalone
    tools/cleanup_orphaned_content.py remains for the one-time historical
    backlog and the anonymization pipeline.)
    """
    total = len(ids)
    deleted = 0
    freed = [0, 0, 0]  # new_text, source, source_text
    t0 = time.time()
    for i in range(0, total, BATCH_SIZE):
        batch = ids[i : i + BATCH_SIZE]
        placeholders = ",".join(str(x) for x in batch)

        # Capture the shared content this batch references, before deleting it.
        text_ids = _ids(
            f"SELECT DISTINCT text_id FROM article_fragment WHERE article_id IN ({placeholders})"
        )
        source_ids = _ids(
            f"SELECT DISTINCT source_id FROM article "
            f"WHERE id IN ({placeholders}) AND source_id IS NOT NULL"
        )
        source_text_ids = []
        if source_ids:
            sph = ",".join(str(s) for s in source_ids)
            source_text_ids = _ids(
                f"SELECT DISTINCT source_text_id FROM source "
                f"WHERE id IN ({sph}) AND source_text_id IS NOT NULL"
            )

        try:
            db_session.execute(
                text(f"DELETE FROM article WHERE id IN ({placeholders})")
            )
            db_session.commit()
        except IntegrityError as e:
            db_session.rollback()
            print(f"\n!!! PRUNE ABORTED after {deleted} deletions.")
            print("    A candidate article is still referenced — the FK below "
                  "blocked its deletion, which means referenced_article_ids() is")
            print("    missing the referencing table. Add it to the pre-filter "
                  "(or, if the data is disposable, make its FK ON DELETE CASCADE)")
            print("    and re-run. No referenced article was force-deleted.")
            print(f"\n    {e.orig}")
            raise

        # Now that the batch's articles (and their fragments) are gone, reclaim
        # the shared content they pointed at that nobody else references.
        nt, ns, nst = reclaim_shared_content(text_ids, source_ids, source_text_ids)
        freed[0] += nt
        freed[1] += ns
        freed[2] += nst
        db_session.commit()

        deleted += len(batch)
        if deleted % 10000 == 0 or deleted == total:
            pct = 100 * deleted // total if total else 100
            print(f"    deleted {deleted}/{total} ({pct}%)")

    print(f"  done in {time.time() - t0:.1f}s")
    print(
        f"  reclaimed shared content: {freed[0]} new_text, "
        f"{freed[1]} source, {freed[2]} source_text"
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
