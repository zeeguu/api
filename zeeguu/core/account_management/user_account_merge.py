"""
Merge one user account (the source) into another (the target).

Developer-only; the CLI is tools/merge_users.py. Everything the source owns is
moved onto the target, and the source is then deactivated, not deleted.

Every (table, column) that references a user must have an entry in POLICIES.
At startup the live schema is reflected (not the models: prod has tables and
unique indexes the models do not declare, and vice versa) and the merge refuses
to run if a user reference has no policy, so a table added later cannot be
silently left behind.

Collisions: a source row whose unique key (live unique indexes, the unique
constraints declared on the models, and EXTRA_KEYS) already exists for the
target cannot be moved. What happens to it depends on the policy:

  MOVE       it stays on the source. The source still exists (deactivated),
             so nothing is destroyed; it just no longer shows up for the target.
  MOVE_DEDUP it is deleted. Used for memberships, where a leftover row would
             put a dead "(merged into N)" account on a teacher's class list.

user_word, friendship and friend_request have dedicated code (SPECIAL).

The whole merge runs in one transaction, each step in a SAVEPOINT so a failure
names the step that caused it. A dry run executes exactly the same statements
and rolls back, so its counts are the counts a real run would produce.
"""

import secrets
from collections import defaultdict

from sqlalchemy import inspect, text

from zeeguu.core.model.db import db

MOVE = "move"
MOVE_DEDUP = "move_dedup"
DELETE = "delete"
SPECIAL = "special"

POLICIES = {
    ("article", "uploader_id"): MOVE,
    ("article_cefr_assessment", "teacher_assessed_by_user_id"): MOVE,
    ("article_difficulty_feedback", "user_id"): MOVE,
    # On collision the source's link stays where it is, so a /read/<code> URL
    # that was already shared keeps resolving.
    ("article_share_link", "user_id"): MOVE,
    ("article_topic_user_feedback", "user_id"): MOVE,
    ("article_upload", "user_id"): MOVE,
    ("audio_lesson_generation_progress", "user_id"): MOVE,
    ("daily_audio_lesson", "user_id"): MOVE,
    ("daily_audio_subscription", "user_id"): MOVE,
    ("example_sentence", "user_id"): MOVE,
    ("exercise_report", "user_id"): MOVE,
    ("meaning_report", "user_id"): MOVE,
    ("personal_copy", "user_id"): MOVE,
    ("search_filter", "user_id"): MOVE,
    ("search_subscription", "user_id"): MOVE,
    ("shared_article", "from_user_id"): MOVE,
    ("shared_article", "to_user_id"): MOVE,
    ("starred_article", "user_id"): MOVE,
    ("starred_words_association", "user_id"): MOVE,
    ("topic_filter", "user_id"): MOVE,
    ("topic_subscription", "user_id"): MOVE,
    ("topic_user_feedback", "user_id"): MOVE,
    ("translation_search", "user_id"): MOVE,
    ("user_activity_data", "user_id"): MOVE,
    ("user_article", "user_id"): MOVE,
    ("user_article_broken_report", "user_id"): MOVE,
    ("user_avatar", "user_id"): MOVE,
    ("user_badge", "user_id"): MOVE,
    ("user_badge_progress", "user_id"): MOVE,
    ("user_browsing_session", "user_id"): MOVE,
    ("user_exercise_session", "user_id"): MOVE,
    ("user_feedback", "user_id"): MOVE,
    # Languages the target lacks move; for a shared language the target's
    # row (level, streak, variety) wins.
    ("user_language", "user_id"): MOVE,
    ("user_listening_session", "user_id"): MOVE,
    ("user_mwe_override", "user_id"): MOVE,
    ("user_notification", "user_id"): MOVE,
    ("user_onboarding_message", "user_id"): MOVE,
    ("user_preference", "user_id"): MOVE,
    ("user_reading_session", "user_id"): MOVE,
    ("user_video", "user_id"): MOVE,
    ("user_watching_session", "user_id"): MOVE,
    ("user_cohort_map", "user_id"): MOVE_DEDUP,
    ("teacher", "user_id"): MOVE_DEDUP,
    ("teacher_cohort_map", "user_id"): MOVE_DEDUP,
    # Login sessions: deleting them logs the source out everywhere.
    ("session", "user_id"): DELETE,
    ("user_word", "user_id"): SPECIAL,
    ("friendship", "user_a_id"): SPECIAL,
    ("friendship", "user_b_id"): SPECIAL,
    ("friend_request", "sender_id"): SPECIAL,
    ("friend_request", "receiver_id"): SPECIAL,
}

# Keys that are unique in practice but not visible to reflection everywhere.
# The first three are unique indexes in prod that the models do not declare
# (listed so the sqlite test DB, built from the models, behaves like prod);
# the last two are logical: one value per key, one teacher row per user.
# A key is the other columns of the unique index, besides the user column.
EXTRA_KEYS = {
    "user_avatar": [()],
    "teacher_cohort_map": [("cohort_id",)],
    "user_onboarding_message": [("onboarding_message_id",)],
    "user_preference": [("key",)],
    "teacher": [()],
}

# Everything that points at a user_word row. Merging two user_words repoints
# these from the dropped row to the kept one. validation_log has no FK, which
# is why this is a list and not derived from reflection alone.
USER_WORD_REFERENCES = [
    ("bookmark", "user_word_id"),
    ("exercise", "user_word_id"),
    ("user_word_interaction_history", "user_word_id"),
    ("validation_log", "user_word_id"),
    ("basic_sr_schedule", "user_word_id"),
]

MERGED_EMAIL_DOMAIN = "merged.zeeguu.invalid"


class MergeError(Exception):
    pass


def _q(name):
    return db.session.get_bind().dialect.identifier_preparer.quote(name)


def _exec(sql, **params):
    return db.session.execute(text(sql), params)


# ---------------------------------------------------------------- reflection


def _inspector():
    # Inspect through the session's connection: with sqlite :memory: a fresh
    # engine connection would see an empty database.
    return inspect(db.session.connection())


def live_references(inspector, referenced_table):
    """(table, column) pairs that reference `referenced_table`.

    Declared FKs plus columns named like a reference that have no FK
    (e.g. article_topic_user_feedback.user_id, validation_log.user_word_id).
    """
    refs = set()
    for table in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table):
            if fk["referred_table"] == referenced_table:
                refs.update((table, c) for c in fk["constrained_columns"])
        for col in inspector.get_columns(table):
            name = col["name"]
            if referenced_table == "user" and (
                name == "user_id" or name.endswith("_user_id")
            ):
                refs.add((table, name))
            if referenced_table == "user_word" and name == "user_word_id":
                refs.add((table, name))
    return refs


def check_policies_cover_schema(inspector):
    missing = sorted(live_references(inspector, "user") - set(POLICIES))
    missing_uw = sorted(
        live_references(inspector, "user_word") - set(USER_WORD_REFERENCES)
    )
    problems = [f"{t}.{c} references user but has no merge policy" for t, c in missing]
    problems += [
        f"{t}.{c} references user_word but is not in USER_WORD_REFERENCES"
        for t, c in missing_uw
    ]
    if problems:
        raise MergeError(
            "Schema has user references this script does not know how to merge:\n  "
            + "\n  ".join(problems)
        )


def collision_keys(inspector, model_uniques, table, column):
    """The other columns of every unique key that includes `column`."""
    keys = set()
    candidates = [
        ix["column_names"] for ix in inspector.get_indexes(table) if ix.get("unique")
    ]
    candidates += [uc["column_names"] for uc in inspector.get_unique_constraints(table)]
    pk = inspector.get_pk_constraint(table)["constrained_columns"]
    if len(pk) > 1:
        candidates.append(pk)
    candidates += model_uniques.get(table, [])
    for cols in candidates:
        if column in cols:
            keys.add(tuple(sorted(c for c in cols if c != column)))
    keys.update(tuple(sorted(k)) for k in EXTRA_KEYS.get(table, []))
    return sorted(keys)


def _model_uniques():
    from sqlalchemy import UniqueConstraint

    uniques = defaultdict(list)
    for table in db.metadata.tables.values():
        for con in table.constraints:
            if isinstance(con, UniqueConstraint):
                uniques[table.name].append([c.name for c in con.columns])
        for ix in table.indexes:
            if ix.unique:
                uniques[table.name].append([c.name for c in ix.columns])
    return uniques


def _row_ids(inspector, table, column):
    """Columns that identify a single row, excluding the user column itself."""
    pk = inspector.get_pk_constraint(table)["constrained_columns"]
    return [c for c in pk if c != column] or pk


# ------------------------------------------------------------ generic steps


def _colliding_rows(table, column, source_id, target_id, keys, id_cols):
    """Source rows whose key already exists for the target, as id dicts."""
    if not keys:
        return []
    key_cols = sorted({c for key in keys for c in key})
    select_cols = ", ".join(_q(c) for c in sorted(set(id_cols) | set(key_cols)))
    select_cols = select_cols or "1"
    sql = f"SELECT {select_cols} FROM {_q(table)} WHERE {_q(column)} = :uid"
    target_rows = [dict(r._mapping) for r in _exec(sql, uid=target_id)]
    source_rows = [dict(r._mapping) for r in _exec(sql, uid=source_id)]

    taken = defaultdict(set)
    for row in target_rows:
        for key in keys:
            values = tuple(row[c] for c in key)
            if None not in values:  # NULLs never collide in a unique index
                taken[key].add(values)

    colliding = []
    for row in source_rows:
        for key in keys:
            values = tuple(row[c] for c in key)
            if None not in values and values in taken[key]:
                colliding.append({c: row[c] for c in id_cols})
                break
    return colliding


def _row_condition(rows, prefix):
    """SQL + params matching exactly `rows` (dicts of id column -> value)."""
    clauses, params = [], {}
    for i, row in enumerate(rows):
        parts = []
        for col, value in row.items():
            name = f"{prefix}{i}_{col}"
            parts.append(f"{_q(col)} = :{name}")
            params[name] = value
        clauses.append("(" + " AND ".join(parts) + ")")
    return " OR ".join(clauses), params


def _merge_table(inspector, model_uniques, table, column, policy, source_id, target_id):
    counts = {}
    if policy == DELETE:
        result = _exec(
            f"DELETE FROM {_q(table)} WHERE {_q(column)} = :src", src=source_id
        )
        counts["deleted"] = result.rowcount
        return counts

    keys = collision_keys(inspector, model_uniques, table, column)
    id_cols = _row_ids(inspector, table, column)
    colliding = _colliding_rows(table, column, source_id, target_id, keys, id_cols)

    exclude, params = "", {"src": source_id, "tgt": target_id}
    if colliding:
        condition, cond_params = _row_condition(colliding, "c")
        params.update(cond_params)
        if policy == MOVE_DEDUP:
            result = _exec(
                f"DELETE FROM {_q(table)} WHERE {_q(column)} = :src AND ({condition})",
                **params,
            )
            counts["deleted (duplicate)"] = result.rowcount
        else:
            exclude = f" AND NOT ({condition})"
            counts["kept on source (collision)"] = len(colliding)

    result = _exec(
        f"UPDATE {_q(table)} SET {_q(column)} = :tgt WHERE {_q(column)} = :src{exclude}",
        **params,
    )
    counts["moved"] = result.rowcount
    return counts


# ------------------------------------------------------------ special steps


def _user_word_rows(user_id):
    return {
        row.meaning_id: row
        for row in _exec(
            """
            SELECT uw.id, uw.meaning_id, uw.fit_for_study, uw.user_preference,
                   uw.learned_time, uw.level, uw.is_user_added,
                   uw.preferred_bookmark_id,
                   (SELECT COUNT(*) FROM bookmark b WHERE b.user_word_id = uw.id)
                       AS bookmark_count,
                   (SELECT MAX(s.cooling_interval) FROM basic_sr_schedule s
                    WHERE s.user_word_id = uw.id) AS cooling_interval,
                   (SELECT COUNT(*) FROM basic_sr_schedule s
                    WHERE s.user_word_id = uw.id) AS schedule_count
            FROM user_word uw WHERE uw.user_id = :uid
            """,
            uid=user_id,
        )
    }


def _richness(uw):
    """Bigger is richer: learned, then further along in practice, then more
    bookmarks. Bookmarks always move to the kept row, so the count only breaks
    ties between rows with the same learning state."""
    return (
        uw.learned_time is not None,
        uw.level or 0,
        uw.cooling_interval if uw.cooling_interval is not None else -1,
        uw.bookmark_count,
    )


def _merge_user_word_pair(keep, drop):
    """Repoint everything from `drop` to `keep`, fill keep's gaps, delete drop."""
    keep_has_schedule = keep.schedule_count > 0
    for table, column in USER_WORD_REFERENCES:
        if table == "basic_sr_schedule" and keep_has_schedule:
            # unique on user_word_id: keep's schedule is the one that stays
            _exec(f"DELETE FROM {_q(table)} WHERE {_q(column)} = :drop", drop=drop.id)
            continue
        _exec(
            f"UPDATE {_q(table)} SET {_q(column)} = :keep WHERE {_q(column)} = :drop",
            keep=keep.id,
            drop=drop.id,
        )

    _exec(
        """
        UPDATE user_word SET
            fit_for_study = COALESCE(fit_for_study, :fit),
            user_preference = COALESCE(user_preference, :pref),
            learned_time = COALESCE(learned_time, :learned),
            is_user_added = CASE WHEN :added = 1 THEN 1 ELSE is_user_added END,
            preferred_bookmark_id = COALESCE(preferred_bookmark_id, :bm)
        WHERE id = :keep
        """,
        fit=drop.fit_for_study,
        pref=drop.user_preference,
        learned=drop.learned_time,
        added=1 if drop.is_user_added else 0,
        bm=drop.preferred_bookmark_id,
        keep=keep.id,
    )
    # preferred_bookmark_id -> bookmark is RESTRICT; clear it before deleting
    _exec("UPDATE user_word SET preferred_bookmark_id = NULL WHERE id = :drop", drop=drop.id)
    _exec("DELETE FROM user_word WHERE id = :drop", drop=drop.id)


def _merge_user_words(source_id, target_id):
    source_words = _user_word_rows(source_id)
    target_words = _user_word_rows(target_id)
    counts = defaultdict(int)

    for meaning_id, src in source_words.items():
        tgt = target_words.get(meaning_id)
        if tgt is None:
            continue
        # ties keep the target's row
        if _richness(src) > _richness(tgt):
            keep, drop = src, tgt
            counts["collisions, source row kept"] += 1
        else:
            keep, drop = tgt, src
            counts["collisions, target row kept"] += 1
        counts["bookmarks repointed"] += drop.bookmark_count
        with db.session.begin_nested():
            _merge_user_word_pair(keep, drop)

    result = _exec(
        "UPDATE user_word SET user_id = :tgt WHERE user_id = :src",
        src=source_id,
        tgt=target_id,
    )
    counts["moved"] = result.rowcount
    return dict(counts)


def _merge_pairs(table, col_a, col_b, source_id, target_id):
    """friendship / friend_request: one row per pair of users, either order.

    A row between source and target is deleted (it would become a user paired
    with themselves), as is a row with someone the target is already paired
    with. Everything else is repointed from the source to the target.
    """
    counts = defaultdict(int)
    rows = _exec(
        f"SELECT id, {col_a} AS a, {col_b} AS b FROM {table} "
        f"WHERE {col_a} = :src OR {col_b} = :src",
        src=source_id,
    ).fetchall()
    target_partners = {
        r.a if r.b == target_id else r.b
        for r in _exec(
            f"SELECT {col_a} AS a, {col_b} AS b FROM {table} "
            f"WHERE {col_a} = :tgt OR {col_b} = :tgt",
            tgt=target_id,
        )
    }
    for row in rows:
        other = row.b if row.a == source_id else row.a
        if other == target_id:
            _exec(f"DELETE FROM {table} WHERE id = :id", id=row.id)
            counts["deleted (between source and target)"] += 1
        elif other in target_partners:
            _exec(f"DELETE FROM {table} WHERE id = :id", id=row.id)
            counts["deleted (duplicate)"] += 1
        else:
            column = col_a if row.a == source_id else col_b
            _exec(f"UPDATE {table} SET {column} = :tgt WHERE id = :id", tgt=target_id, id=row.id)
            target_partners.add(other)
            counts["moved"] += 1
    return dict(counts)


# ------------------------------------------------------------ users


def _deactivate(source, target, take_email):
    original_email = source.email
    source.email = f"merged-{source.id}-into-{target.id}@{MERGED_EMAIL_DOMAIN}"
    source.update_password(secrets.token_urlsafe(48))
    source.email_verified = False
    source.name = f"{source.name} (merged into {target.id})"[:255]
    db.session.flush()  # free the address before the target can take it

    if take_email:
        target.email = original_email
        target.email_verified = False

    if source.created_at and (not target.created_at or source.created_at < target.created_at):
        target.created_at = source.created_at
    if source.last_seen and (not target.last_seen or source.last_seen > target.last_seen):
        target.last_seen = source.last_seen
    db.session.flush()


def remaining_counts(inspector, source_id):
    """Rows still pointing at the source, per (table, column)."""
    live = live_references(inspector, "user")
    counts = {}
    for table, column in sorted(live):
        n = _exec(
            f"SELECT COUNT(*) FROM {_q(table)} WHERE {_q(column)} = :src", src=source_id
        ).scalar()
        if n:
            counts[(table, column)] = n
    return counts


def merge_users(source, target, take_email=False, log=print):
    """Merge `source` into `target` inside the current transaction.

    Does not commit: the caller commits or rolls back (that is the dry run).
    Returns {step: {outcome: count}}.
    """
    if source.id == target.id:
        raise MergeError("source and target are the same user")
    for u in (source, target):
        if u.email and u.email.endswith("@" + MERGED_EMAIL_DOMAIN):
            raise MergeError(f"user {u.id} was already merged into another account")

    inspector = _inspector()
    check_policies_cover_schema(inspector)
    model_uniques = _model_uniques()
    live = live_references(inspector, "user")

    report = {}

    def step(name, fn):
        try:
            with db.session.begin_nested():
                report[name] = fn()
        except Exception as e:
            raise MergeError(f"step {name} failed: {e}") from e
        log(f"  {name:<52} {_fmt(report[name])}")

    step("user_word.user_id", lambda: _merge_user_words(source.id, target.id))
    step(
        "friendship",
        lambda: _merge_pairs("friendship", "user_a_id", "user_b_id", source.id, target.id),
    )
    step(
        "friend_request",
        lambda: _merge_pairs("friend_request", "sender_id", "receiver_id", source.id, target.id),
    )

    for (table, column), policy in sorted(POLICIES.items()):
        if policy == SPECIAL or (table, column) not in live:
            continue
        step(
            f"{table}.{column}",
            lambda t=table, c=column, p=policy: _merge_table(
                inspector, model_uniques, t, c, p, source.id, target.id
            ),
        )

    step("user (deactivate source)", lambda: _deactivate(source, target, take_email) or {})

    # Anything left on the source must be exactly the collisions kept on
    # purpose; otherwise a step silently missed rows.
    expected = {
        tuple(name.split(".")): counts.get("kept on source (collision)", 0)
        for name, counts in report.items()
        if "." in name
    }
    for ref, n in remaining_counts(inspector, source.id).items():
        if expected.get(ref, 0) != n:
            raise MergeError(
                f"{ref[0]}.{ref[1]}: {n} rows still on the source, "
                f"expected {expected.get(ref, 0)}"
            )

    dupes = _exec(
        "SELECT COUNT(*) FROM (SELECT meaning_id FROM user_word WHERE user_id = :tgt "
        "GROUP BY meaning_id HAVING COUNT(*) > 1) d",
        tgt=target.id,
    ).scalar()
    if dupes:
        raise MergeError(f"target ends up with {dupes} duplicate (user_id, meaning_id) rows")

    return report


def _fmt(counts):
    if not counts:
        return "-"
    return ", ".join(f"{k}: {v}" for k, v in counts.items() if v) or "-"
