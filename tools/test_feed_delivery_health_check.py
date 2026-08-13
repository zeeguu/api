#!/usr/bin/env python
"""
Unit tests for the PURE classification logic of the feed delivery health check.

The full ES + DB delivery path (segment_inventory_published_times,
canary_published_times, active_users_by_segment) is hard to unit-test — it needs
a live Elasticsearch index and a populated MySQL — so it's exercised manually /
in staging, not here. What we CAN and do pin down below is the freshness +
staleness classification and the segment-status decision, which is where the
thresholds live and where a regression would silently change what alerts.

These tests import the module directly; per its module note, importing does NOT
create a Flask app or touch the DB, so no fixtures are needed.

Run:
    python -m pytest tools/test_feed_delivery_health_check.py -v
"""

from datetime import datetime, timedelta

from tools.feed_delivery_health_check import (
    freshness_summary,
    classify_segment,
    is_alerting,
    Segment,
    SegmentResult,
    FreshnessSummary,
    STATUS_OK,
    STATUS_EMPTY,
    STATUS_NO_FRESH,
    STATUS_STALE,
)


def _result(cefr_level, status):
    return SegmentResult(
        Segment("da", cefr_level), status, "reason",
        FreshnessSummary(0, 0, None), None, None, None, "",
    )

NOW = datetime(2026, 8, 13, 12, 0, 0)


def _days_ago(n):
    return NOW - timedelta(days=n)


# --- freshness_summary --------------------------------------------------------
def test_freshness_summary_empty():
    s = freshness_summary([], NOW, fresh_days=7)
    assert s == FreshnessSummary(0, 0, None)


def test_freshness_summary_ignores_none_entries():
    s = freshness_summary([None, _days_ago(1), None], NOW, fresh_days=7)
    assert s.total == 1
    assert s.fresh_count == 1


def test_freshness_summary_counts_fresh_within_window():
    times = [_days_ago(1), _days_ago(3), _days_ago(6), _days_ago(10), _days_ago(30)]
    s = freshness_summary(times, NOW, fresh_days=7)
    assert s.total == 5
    # 1, 3, 6 days old are < 7d; 10 and 30 are not.
    assert s.fresh_count == 3


def test_freshness_summary_freshest_age_is_the_newest():
    times = [_days_ago(2), _days_ago(9), _days_ago(4)]
    s = freshness_summary(times, NOW, fresh_days=7)
    # freshest = 2 days old
    assert abs(s.freshest_age_days - 2.0) < 1e-6


def test_freshness_summary_boundary_is_strict():
    # Exactly at the cutoff is NOT counted as fresh (> cutoff, strict).
    s = freshness_summary([_days_ago(7)], NOW, fresh_days=7)
    assert s.fresh_count == 0


# --- classify_segment ---------------------------------------------------------
def test_classify_ok():
    s = FreshnessSummary(total=8, fresh_count=5, freshest_age_days=1.0)
    status, _ = classify_segment(s, min_articles=3, min_fresh=3, stale_days=4)
    assert status == STATUS_OK


def test_classify_empty_when_too_few_items():
    s = FreshnessSummary(total=2, fresh_count=2, freshest_age_days=0.5)
    status, reason = classify_segment(s, min_articles=3, min_fresh=3, stale_days=4)
    assert status == STATUS_EMPTY
    assert "recommendable" in reason


def test_classify_empty_takes_precedence_over_fresh_check():
    # Zero items -> EMPTY, not NO_FRESH, even though fresh_count also < min_fresh.
    s = FreshnessSummary(total=0, fresh_count=0, freshest_age_days=None)
    status, _ = classify_segment(s, min_articles=3, min_fresh=3, stale_days=4)
    assert status == STATUS_EMPTY


def test_classify_no_fresh_when_inventory_exists_but_stale():
    # This is the incident shape: plenty of items, but not enough FRESH ones.
    s = FreshnessSummary(total=20, fresh_count=1, freshest_age_days=9.0)
    status, reason = classify_segment(s, min_articles=3, min_fresh=3, stale_days=4)
    assert status == STATUS_NO_FRESH
    assert "fresh" in reason


def test_classify_stale_when_fresh_enough_but_freshest_too_old():
    # Enough "fresh" (within 7d) items to pass min_fresh, but the freshest is
    # older than stale_days -> STALE. Uses a wider fresh window than stale window.
    s = FreshnessSummary(total=10, fresh_count=4, freshest_age_days=5.0)
    status, reason = classify_segment(s, min_articles=3, min_fresh=3, stale_days=4)
    assert status == STATUS_STALE
    assert "freshest" in reason


def test_classify_ok_at_stale_boundary():
    # freshest exactly == stale_days is NOT stale (strict >).
    s = FreshnessSummary(total=10, fresh_count=5, freshest_age_days=4.0)
    status, _ = classify_segment(s, min_articles=3, min_fresh=3, stale_days=4)
    assert status == STATUS_OK


# --- is_alerting (alert-level gating) -----------------------------------------
ALERTING = {"A1", "A2", "B1", "B2"}


def test_alerting_when_failing_and_level_in_alert_set():
    assert is_alerting(_result("B2", STATUS_STALE), ALERTING) is True


def test_not_alerting_for_report_only_level_even_when_empty():
    # C1/C2 are report-only until we complexify — empty must NOT alert.
    assert is_alerting(_result("C1", STATUS_EMPTY), ALERTING) is False
    assert is_alerting(_result("C2", STATUS_NO_FRESH), ALERTING) is False


def test_not_alerting_when_segment_is_ok():
    assert is_alerting(_result("B1", STATUS_OK), ALERTING) is False
