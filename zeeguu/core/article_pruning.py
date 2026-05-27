"""Shared, safe article-deletion logic.

Used by both tools/prune_old_articles.py (age-based retention pruning) and
tools/anonymize_users.py (delete all unreferenced articles). Having one
implementation means neither can drift into re-creating orphans.

Design (see also migration 26-05-26--restrict-article-fk-for-prune-protection):
  - Delete with FK checks ON. The DB cascades each article's OWNED children
    (fragments, tokenization cache, cefr/classification/topic maps, and
    simplified children via parent_article_id) automatically.
  - Tables holding data we keep block the delete (RESTRICT / NO ACTION).
    referenced_article_ids() pre-filters those so we don't attempt doomed
    deletes; if it ever drifts out of sync with the FKs, the delete is blocked
    and we ABORT LOUDLY naming the constraint, rather than silently skipping.
  - The shared, de-duplicated content tables (new_text / source / source_text)
    have no FK from article, so the cascade can't reach them; we reclaim them
    inline per batch, scoped to the ids the batch touched (no full-table scan),
    guarded by NOT EXISTS so rows still used by a surviving article / bookmark /
    caption are kept.
"""

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Every table with a RESTRICT / NO ACTION foreign key on article.article_id:
# an article referenced by any of these must NOT be deleted. Keep in sync with
#   SELECT TABLE_NAME FROM information_schema.REFERENTIAL_CONSTRAINTS
#   WHERE REFERENCED_TABLE_NAME='article' AND DELETE_RULE IN ('RESTRICT','NO ACTION');
PROTECTING_TABLES = [
    "user_article",
    "text",
    "user_reading_session",
    "personal_copy",
    "cohort_article_map",
    "user_activity_data",
    "article_topic_user_feedback",
    "user_article_broken_report",
    "article_summary_context",
    "article_title_context",
    "article_difficulty_feedback",
    "topic_user_feedback",
    "user_mwe_override",
]

BATCH_SIZE = 1000


def _ids(db_session, sql):
    return [r[0] for r in db_session.execute(text(sql))]


def referenced_article_ids(db_session, verbose=True):
    """Set of article ids that must never be pruned (referenced by kept data)."""
    if verbose:
        print("Building reference set...")
    ref = set()
    for tbl in PROTECTING_TABLES:
        before = len(ref)
        ref.update(
            r[0]
            for r in db_session.execute(
                text(f"SELECT DISTINCT article_id FROM {tbl} WHERE article_id IS NOT NULL")
            )
        )
        if verbose:
            print(f"  {tbl}: +{len(ref) - before} (total {len(ref)})")

    # Activity can reference an article via source_id -> article.source_id.
    source_ids = set(
        r[0]
        for r in db_session.execute(
            text("SELECT DISTINCT source_id FROM user_activity_data WHERE source_id IS NOT NULL")
        )
    )
    if source_ids:
        ph = ",".join(str(s) for s in source_ids)
        before = len(ref)
        ref.update(_ids(db_session, f"SELECT id FROM article WHERE source_id IN ({ph})"))
        if verbose:
            print(f"  user_activity_data via source_id: +{len(ref) - before} (total {len(ref)})")

    # Protect the ORIGINAL of any referenced simplification: parent_article_id
    # is ON DELETE CASCADE, so deleting an original would cascade to (and be
    # blocked by) a still-referenced simplification. Keeping the original keeps
    # the family together and never orphans a simplification. (One level.)
    if ref:
        ph = ",".join(str(a) for a in ref)
        before = len(ref)
        ref.update(
            _ids(
                db_session,
                f"SELECT DISTINCT parent_article_id FROM article "
                f"WHERE id IN ({ph}) AND parent_article_id IS NOT NULL",
            )
        )
        if verbose:
            print(f"  originals of referenced simplifications: +{len(ref) - before} (total {len(ref)})")

    return ref


def reclaim_shared_content(db_session, text_ids, source_ids, source_text_ids):
    """Delete the de-duplicated content a just-pruned batch pointed at, but only
    rows now referenced by nobody. Returns (n_new_text, n_source, n_source_text)."""
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


def delete_articles_in_batches(db_session, ids, batch_size=BATCH_SIZE):
    """Delete the given article ids with FK checks ON, reclaiming their shared
    content inline. Aborts loudly (re-raising, naming the FK) if any delete is
    blocked — meaning referenced_article_ids() missed a protecting table."""
    import time

    total = len(ids)
    deleted = 0
    freed = [0, 0, 0]  # new_text, source, source_text
    t0 = time.time()
    for i in range(0, total, batch_size):
        batch = ids[i : i + batch_size]
        ph = ",".join(str(x) for x in batch)

        text_ids = _ids(
            db_session, f"SELECT DISTINCT text_id FROM article_fragment WHERE article_id IN ({ph})"
        )
        source_ids = _ids(
            db_session,
            f"SELECT DISTINCT source_id FROM article WHERE id IN ({ph}) AND source_id IS NOT NULL",
        )
        source_text_ids = []
        if source_ids:
            sph = ",".join(str(s) for s in source_ids)
            source_text_ids = _ids(
                db_session,
                f"SELECT DISTINCT source_text_id FROM source "
                f"WHERE id IN ({sph}) AND source_text_id IS NOT NULL",
            )

        try:
            db_session.execute(text(f"DELETE FROM article WHERE id IN ({ph})"))
            db_session.commit()
        except IntegrityError as e:
            db_session.rollback()
            print(f"\n!!! ABORTED after {deleted} deletions.")
            print("    An article is still referenced — the FK below blocked its")
            print("    deletion, so referenced_article_ids() is missing a table.")
            print("    Add it to PROTECTING_TABLES (or, if disposable, make its FK")
            print("    ON DELETE CASCADE) and re-run. No referenced data was lost.")
            print(f"\n    {e.orig}")
            raise

        nt, ns, nst = reclaim_shared_content(db_session, text_ids, source_ids, source_text_ids)
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
    return deleted
