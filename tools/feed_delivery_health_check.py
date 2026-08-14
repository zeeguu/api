#!/usr/bin/env python
"""
Feed DELIVERY health check — does a real user in each segment actually SEE a
fresh feed?

Why this exists (the motivating incident)
-----------------------------------------
We already have supply-side checks: crawler_liveness_check.py ("is the crawler
alive at all?") and feed_health_check.py ("which individual RSS feeds went
quiet?"). Both watch the DOWNLOAD side. But in Aug 2026 a real user's feed was
silently EMPTY for ~5 days while downloads were perfectly fine: the
simplification pipeline had broken, and that user's segment (Danish, B2+) is
filtered toward simplified content — of which, suddenly, there was none. A
supply/download check cannot see that: articles WERE arriving, they just never
reached that user's feed after CEFR + feature-flag filtering.

So this check runs on the DELIVERY side. It sweeps the segment matrix — the
dimension that matters is (learned_language, CEFR_level), because feed inventory
and filters vary along it and the incident hit one specific corner — and per
segment asks: is there fresh, recommendable content, and does a real active
user in that segment actually get a non-empty, fresh feed?

Two signals per segment
------------------------
1. INVENTORY (primary alert trigger): re-run the app's OWN recommender query
   builder (build_elastic_recommender_query) parameterized by the segment's
   language + CEFR level, with NO per-user seen-exclusion and NO topic
   narrowing. This is "does fresh content that this segment COULD be shown even
   exist in the index?" It replicates the exact CEFR filtering
   (available_cefr_levels) that starved the incident's segment, without being
   confounded by one user's reading history.

2. PER-USER CANARY (corroboration): pick a real, recently-active user in the
   segment and call the REAL feed function article_recommendations_for_user().
   This exercises the full path the app uses — CEFR filtering, the feature flags
   (simplified-only vs originals-first, "show easier"), the disturbing filter,
   the ES index, seen-exclusion, teacher-upload filtering.

INVENTORY is the primary trigger because a single power-user can legitimately
have an empty PERSONAL feed (they already opened everything fresh) — that's a
false positive for "the segment is broken." Segment-wide inventory has no such
per-user history, so an empty/stale inventory is the trustworthy alarm; the
per-user run is reported alongside as corroboration and as a reality check on
the flags.

Alerting mirrors the other monitors: on failure we email a per-segment summary
via ZeeguuMailer (the app's own SMTP — cron stdout goes to an unread log), log a
structured summary, and exit non-zero so cron surfaces it.

NOTE: not wired into cron here. Propose the crontab line in the PR; the crontab
source of truth is the OPS repo.

Usage:
    python -m tools.feed_delivery_health_check [--verbose] [--dry-run]
        [--active-days N] [--fresh-days N] [--min-articles K]
        [--min-fresh K] [--stale-days N] [--count N]
        [--languages da,de,...]
"""

import argparse
import os
import sys
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta

from zeeguu.core.model import User, Language
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

# NOTE: the Flask app + app context are created inside main(), NOT at module
# import time. The DB-touching functions below need an app context at CALL time,
# but the pure classification helpers (freshness_summary, classify_segment) do
# not — keeping app creation out of import lets the unit tests import this module
# without a DB / config, and keeps `python -m tools...` behavior unchanged.


# --- Thresholds ---------------------------------------------------------------
# These are STARTING GUESSES to tune once we have a few weeks of real numbers per
# segment (see OPEN QUESTIONS in the PR). Each is env-overridable so cron can
# adjust without a code change.
def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_level_set(name, default):
    raw = os.environ.get(name, default)
    return {tok.strip().upper() for tok in raw.split(",") if tok.strip()}


# Consider a user "active" if last_seen within this window.
ACTIVE_DAYS = _env_int("FEED_HEALTH_ACTIVE_DAYS", 30)
# An article/video counts as FRESH if published within this window.
FRESH_DAYS = _env_int("FEED_HEALTH_FRESH_DAYS", 7)
# A segment needs at least this many recommendable items total...
MIN_ARTICLES = _env_int("FEED_HEALTH_MIN_ARTICLES", 3)
# ...and at least this many of them FRESH.
MIN_FRESH = _env_int("FEED_HEALTH_MIN_FRESH", 3)
# Flag a segment if even its FRESHEST recommendable item is older than this.
# We crawl several times a day, so for an alerting segment "nothing fresh in ~a
# day" already means new content stopped landing — that's the alarm, not a
# multi-day grace. Kept at 1 (≈ nothing new today); this assumes the check runs
# AFTER the day's crawl so it doesn't fire on a not-yet-crawled today.
STALE_DAYS = _env_int("FEED_HEALTH_STALE_DAYS", 1)
# CEFR levels whose failures actually ALERT (email + non-zero exit). Other levels
# are still evaluated and shown in the report, but don't trigger alerts. C1/C2
# are report-only by default: we don't complexify (generate above-level content)
# yet, so almost all crawled news sits at A1–B2 and C1/C2 are empty by design —
# alerting on them would be pure noise. Revisit when complexification ships.
ALERT_LEVELS = _env_level_set("FEED_HEALTH_ALERT_LEVELS", "A1,A2,B1,B2")
# How many items to request from the recommender / inventory query.
COUNT = _env_int("FEED_HEALTH_COUNT", 10)


# --- Pure classification logic (unit-tested) ----------------------------------
# Kept free of ES/DB so the freshness + status logic can be tested with plain
# datetimes and a small fixture (see tools/test/test_feed_delivery_health_check.py).

FreshnessSummary = namedtuple(
    "FreshnessSummary", ["total", "fresh_count", "freshest_age_days"]
)


def freshness_summary(published_times, now, fresh_days=FRESH_DAYS):
    """Summarize a list of publication datetimes.

    Returns total count, how many are fresh (published within fresh_days), and
    the age in days of the FRESHEST (newest) item — None when the list is empty.
    """
    times = [t for t in published_times if t is not None]
    total = len(times)
    if total == 0:
        return FreshnessSummary(0, 0, None)

    cutoff = now - timedelta(days=fresh_days)
    fresh_count = sum(1 for t in times if t > cutoff)
    freshest = max(times)
    freshest_age_days = (now - freshest).total_seconds() / 86400.0
    return FreshnessSummary(total, fresh_count, freshest_age_days)


# Segment status values.
STATUS_OK = "OK"
STATUS_EMPTY = "EMPTY"  # nothing (or too little) recommendable at all
STATUS_NO_FRESH = "NO_FRESH"  # inventory exists but not enough of it fresh
STATUS_STALE = "STALE"  # freshest item is older than STALE_DAYS
STATUS_ERROR = "ERROR"  # inventory probe itself failed (ES down/timeout) — infra, not content

FAILING_STATUSES = {STATUS_EMPTY, STATUS_NO_FRESH, STATUS_STALE, STATUS_ERROR}


def is_alerting(result, alert_levels=ALERT_LEVELS):
    """Whether a failing segment should actually raise an alert (email + non-zero
    exit). A segment alerts only if it's failing AND its CEFR level is in the
    alerting set; report-only levels (e.g. C1/C2) are still shown but never
    alarm — see ALERT_LEVELS."""
    return (
        result.status in FAILING_STATUSES
        and result.segment.cefr_level in alert_levels
    )


def classify_segment(
    summary,
    min_articles=MIN_ARTICLES,
    min_fresh=MIN_FRESH,
    stale_days=STALE_DAYS,
):
    """Turn a FreshnessSummary into a segment status + human reason.

    Precedence: EMPTY (not enough content at all) > NO_FRESH (enough content but
    too little of it fresh) > STALE (freshest item too old) > OK. Pure function.
    """
    if summary.total < min_articles:
        return STATUS_EMPTY, (
            f"only {summary.total} recommendable item(s) "
            f"(need >= {min_articles})"
        )
    if summary.fresh_count < min_fresh:
        return STATUS_NO_FRESH, (
            f"only {summary.fresh_count} fresh item(s) "
            f"(need >= {min_fresh}); freshest is "
            f"{_fmt_age(summary.freshest_age_days)} old"
        )
    if summary.freshest_age_days is not None and summary.freshest_age_days > stale_days:
        return STATUS_STALE, (
            f"freshest recommendable item is "
            f"{_fmt_age(summary.freshest_age_days)} old "
            f"(> {stale_days}d)"
        )
    return STATUS_OK, (
        f"{summary.total} items, {summary.fresh_count} fresh, "
        f"freshest {_fmt_age(summary.freshest_age_days)} old"
    )


def _fmt_age(age_days):
    if age_days is None:
        return "n/a"
    return f"{age_days:.1f}d"


# --- Segment matrix -----------------------------------------------------------
Segment = namedtuple("Segment", ["language_code", "cefr_level"])

SegmentResult = namedtuple(
    "SegmentResult",
    [
        "segment",
        "status",
        "reason",
        "inventory_summary",
        "canary_user_id",
        "canary_total",
        "canary_fresh",
        "canary_note",
    ],
)


def active_users_by_segment(active_days, language_codes=None):
    """Group recently-active users into (language, cefr_level) segments.

    Returns dict[Segment] -> list of (user, last_seen), each list sorted with the
    most-recently-seen user first. Users whose CEFR level can't be resolved (no
    UserLanguage row / null level) are skipped. CEFR levels are resolved in ONE
    batched query rather than per-user, to avoid an N+1 over every active user.
    """
    from zeeguu.core.model.user_language import UserLanguage

    cutoff = datetime.now() - timedelta(days=active_days)
    users = (
        User.query.filter(User.last_seen != None)  # noqa: E711
        .filter(User.last_seen >= cutoff)
        .all()
    )

    # Batch: one query for these users' UserLanguage rows -> {(user_id,
    # language_id): cefr_level int}, where cefr_level is 1..6 (A1..C2).
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    ul_rows = UserLanguage.query.filter(
        UserLanguage.user_id.in_([u.id for u in users])
    ).all()
    cefr_int_by_user_lang = {
        (ul.user_id, ul.language_id): ul.cefr_level for ul in ul_rows
    }

    segments = defaultdict(list)
    for user in users:
        lang = user.learned_language
        if lang is None:
            continue
        if language_codes and lang.code not in language_codes:
            continue
        level_int = cefr_int_by_user_lang.get((user.id, lang.id))
        if not level_int or not (1 <= level_int <= 6):
            continue
        segments[Segment(lang.code, levels[level_int - 1])].append(
            (user, user.last_seen)
        )

    for seg in segments:
        segments[seg].sort(key=lambda pair: pair[1], reverse=True)
    return segments


# --- ES inventory (primary signal) --------------------------------------------
def segment_inventory_published_times(segment, count):
    """Fresh-inventory probe for a segment, independent of any one user.

    Reuses the app's OWN query builder (build_elastic_recommender_query) with the
    segment's language + CEFR level and NO per-user filters (no seen-exclusion,
    no topic narrowing, no disturbing filter). include_lower=False on purpose:
    the incident hit users who see ONLY their exact level, so the strict same-
    level query is the worst-case signal we want to alarm on.

    LIMITATION: this models CEFR filtering but NOT per-user feature-flag filtering
    (e.g. a simplified-only feed). A flag-driven emptiness — like the ORIGINAL
    Aug 2026 incident (simplified-only feed, no simplified content) — would show
    only in the per-user canary, not here. That's acceptable because api#698 made
    feeds originals-first for everyone, removing that filter; revisit if a
    per-user filter that can starve a feed is ever reintroduced.

    Returns a list of publication datetimes for the returned hits (articles AND
    videos), or raises on ES failure (caller treats that as its own alert).
    """
    from elasticsearch import Elasticsearch
    from zeeguu.core.elastic.elastic_query_builder import (
        build_elastic_recommender_query,
    )
    from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX

    language = Language.find(segment.language_code)

    query_body = build_elastic_recommender_query(
        count,
        user_topics="",
        unwanted_user_topics="",
        language=language,
        user_cefr_level=segment.cefr_level,
        es_scale="1d",
        es_offset="1d",
        es_decay=0.6,
        topics_to_include="",
        topics_to_exclude="",
        user_ignored_sources=[],
        articles_to_exclude=None,
        filter_disturbing=False,
        include_lower=False,
        page=0,
    )

    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)
    hits = res["hits"].get("hits", [])
    return [_hit_published_time(h) for h in hits]


def _to_local_naive(dt):
    """Align a datetime to the basis the freshness math uses (datetime.now(), i.e.
    server-local, naive). A tz-aware value is CONVERTED to local first, so a UTC
    timestamp isn't mis-aged by the server's UTC offset; a naive value is assumed
    already local and returned unchanged."""
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.replace(tzinfo=None)


def _hit_published_time(hit):
    """Parse published_time out of an ES hit's _source into a server-local naive
    datetime (matching datetime.now())."""
    raw = hit.get("_source", {}).get("published_time")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return _to_local_naive(raw)
    from dateutil import parser as date_parser

    try:
        return _to_local_naive(date_parser.parse(raw))
    except (ValueError, TypeError):
        return None


# --- Per-user canary (corroboration) ------------------------------------------
def canary_published_times(user, count):
    """Run the REAL feed function for a user and return the publication datetimes
    of what it would show them. Exercises the full delivery path (flags, seen-
    exclusion, everything)."""
    from zeeguu.core.content_recommender.elastic_recommender import (
        article_recommendations_for_user,
    )

    content = article_recommendations_for_user(user, count)
    return [getattr(c, "published_time", None) for c in content]


# --- Orchestration ------------------------------------------------------------
def evaluate_segment(segment, users, count, now, thresholds):
    """Evaluate one segment: inventory (primary) + canary (corroboration)."""
    min_articles, min_fresh, stale_days, fresh_days = thresholds

    # Primary: segment inventory.
    try:
        inv_times = segment_inventory_published_times(segment, count)
        inv_summary = freshness_summary(inv_times, now, fresh_days)
        status, reason = classify_segment(
            inv_summary, min_articles, min_fresh, stale_days
        )
    except Exception as e:
        # Infra failure (ES down/timeout), NOT content emptiness — distinct status
        # so a transient ES hiccup isn't reported as "the segment has no content".
        empty = FreshnessSummary(0, 0, None)
        return SegmentResult(
            segment, STATUS_ERROR, f"inventory query failed: {e}", empty,
            None, None, None, "inventory query raised",
        )

    # Corroboration: per-user canary. Pick a MEDIAN-activity user, not the most
    # recently seen: the heaviest reader's personal feed is legitimately empty most
    # days (they opened everything fresh), which would make corroboration useless.
    canary_user_id = canary_total = canary_fresh = None
    canary_note = ""
    if users:
        canary_user = users[len(users) // 2][0]
        canary_user_id = canary_user.id
        try:
            can_times = canary_published_times(canary_user, count)
            can_summary = freshness_summary(can_times, now, fresh_days)
            canary_total = can_summary.total
            canary_fresh = can_summary.fresh_count
            if can_summary.total == 0:
                # Could be a real power-user who exhausted the fresh feed — that's
                # exactly why the canary is corroboration, not the trigger.
                canary_note = (
                    "canary feed EMPTY (may be a power-user who already opened "
                    "everything fresh — inventory is the authoritative signal)"
                )
            else:
                canary_note = (
                    f"canary sees {can_summary.total} item(s), "
                    f"{can_summary.fresh_count} fresh"
                )
        except Exception as e:
            canary_note = f"canary run failed: {e}"
    else:
        canary_note = "no active user available as canary"

    return SegmentResult(
        segment, status, reason, inv_summary,
        canary_user_id, canary_total, canary_fresh, canary_note,
    )


def build_report(results, alert_levels=ALERT_LEVELS):
    """Human-readable, structured per-segment summary lines."""
    lines = []
    alerting = [r for r in results if is_alerting(r, alert_levels)]
    report_only = [
        r
        for r in results
        if r.status in FAILING_STATUSES and not is_alerting(r, alert_levels)
    ]

    lines.append("=== FEED DELIVERY HEALTH — per-segment summary ===")
    lines.append(f"Checked at {datetime.now():%Y-%m-%d %H:%M}")
    lines.append(
        f"Segments checked: {len(results)}  |  alerting: {len(alerting)}"
        f"  |  report-only issues: {len(report_only)}"
    )
    lines.append("")

    if alerting:
        lines.append("--- ALERTING SEGMENTS (empty/stale) ---")
        for r in sorted(alerting, key=lambda r: (r.segment.language_code, r.segment.cefr_level)):
            lines.extend(_segment_lines(r))
        lines.append("")

    if report_only:
        lines.append("--- REPORT-ONLY ISSUES (not alerting; e.g. C1/C2) ---")
        for r in sorted(report_only, key=lambda r: (r.segment.language_code, r.segment.cefr_level)):
            lines.extend(_segment_lines(r))
        lines.append("")

    lines.append("--- ALL SEGMENTS ---")
    for r in sorted(results, key=lambda r: (r.segment.language_code, r.segment.cefr_level)):
        s = r.segment
        lines.append(
            f"  [{s.language_code} {s.cefr_level}] {r.status}: {r.reason}"
        )
    return lines


def _segment_lines(r):
    s = r.segment
    inv = r.inventory_summary
    out = [
        f"  [{s.language_code} {s.cefr_level}] {r.status}",
        f"      inventory: {inv.total} items, {inv.fresh_count} fresh, "
        f"freshest {_fmt_age(inv.freshest_age_days)} old — {r.reason}",
    ]
    if r.canary_user_id is not None:
        out.append(f"      canary (user {r.canary_user_id}): {r.canary_note}")
    else:
        out.append(f"      canary: {r.canary_note}")
    return out


def main():
    parser = argparse.ArgumentParser(description="Feed delivery health check")
    parser.add_argument("--active-days", type=int, default=ACTIVE_DAYS)
    parser.add_argument("--fresh-days", type=int, default=FRESH_DAYS)
    parser.add_argument("--min-articles", type=int, default=MIN_ARTICLES)
    parser.add_argument("--min-fresh", type=int, default=MIN_FRESH)
    parser.add_argument("--stale-days", type=int, default=STALE_DAYS)
    parser.add_argument("--count", type=int, default=COUNT)
    parser.add_argument(
        "--alert-levels",
        type=str,
        default=",".join(sorted(ALERT_LEVELS)),
        help="Comma-separated CEFR levels whose failures alert; others are report-only.",
    )
    parser.add_argument(
        "--languages",
        type=str,
        default=None,
        help="Comma-separated language codes to restrict to (e.g. da,de).",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do everything except send the alert email.",
    )
    args = parser.parse_args()

    # Create the app + push context here (see module note): tools that query the
    # DB must run under an app context (per the worktree CLAUDE.md), but doing it
    # lazily here keeps the module import-safe for unit tests.
    from zeeguu.api.app import create_app_for_scripts

    app = create_app_for_scripts()
    app.app_context().push()

    language_codes = (
        {c.strip() for c in args.languages.split(",") if c.strip()}
        if args.languages
        else None
    )
    thresholds = (args.min_articles, args.min_fresh, args.stale_days, args.fresh_days)
    now = datetime.now()

    segments = active_users_by_segment(args.active_days, language_codes)
    if not segments:
        print("No active users found in any segment — nothing to check.")
        return 0

    results = []
    for segment in sorted(segments, key=lambda s: (s.language_code, s.cefr_level)):
        users = segments[segment]
        result = evaluate_segment(segment, users, args.count, now, thresholds)
        results.append(result)
        if args.verbose:
            for line in _segment_lines(result):
                print(line)

    alert_levels = {
        t.strip().upper() for t in args.alert_levels.split(",") if t.strip()
    }
    report = build_report(results, alert_levels)
    print("\n".join(report))

    alerting_failures = [r for r in results if is_alerting(r, alert_levels)]
    report_only_failures = [
        r
        for r in results
        if r.status in FAILING_STATUSES and not is_alerting(r, alert_levels)
    ]
    if not alerting_failures:
        note = (
            f" ({len(report_only_failures)} report-only issue(s) shown above)"
            if report_only_failures
            else ""
        )
        print(f"\nOK: no alerting segment failures.{note}")
        return 0

    subject = (
        f"⚠️ Zeeguu feed delivery: {len(alerting_failures)} segment(s) failing (empty/stale/error)"
    )
    if args.dry_run:
        print(f"\n[dry-run] would email: {subject}")
    else:
        ZeeguuMailer.send_mail(subject, report)

    return 1


if __name__ == "__main__":
    sys.exit(main())
