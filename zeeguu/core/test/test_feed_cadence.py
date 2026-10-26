"""
The rules that scale the stale-feed alert and the ephemeral pruning window by
how often a feed publishes (zeeguu/core/feed_cadence.py).
"""

from datetime import datetime, timedelta

from zeeguu.core.feed_cadence import (
    EPHEMERAL_DEFAULT_DAYS,
    PRUNE_MAX_DAYS,
    PRUNE_MIN_DAYS,
    ephemeral_retention_days,
    stale_after,
    typical_gap_hours,
)

NOW = datetime(2026, 10, 26, 12, 0)


def test_gap_is_the_average_time_between_articles():
    # 90 articles over 90 days: one a day
    assert typical_gap_hours(90, NOW - timedelta(days=90), NOW) == 24


def test_gap_is_measured_from_the_oldest_article_so_a_new_feed_is_not_slow():
    # A feed added a week ago with 14 articles posts twice a day
    assert typical_gap_hours(14, NOW - timedelta(days=7), NOW) == 12


def test_too_few_articles_give_no_gap():
    assert typical_gap_hours(2, NOW - timedelta(days=30), NOW) is None
    assert typical_gap_hours(0, None, NOW) is None


def test_unknown_gap_is_stale_after_three_days():
    assert stale_after(None) == timedelta(days=3)


def test_a_fast_feed_is_never_stale_before_three_days():
    assert stale_after(1) == timedelta(days=3)


def test_a_weekly_blog_is_stale_after_three_weeks():
    assert stale_after(7 * 24) == timedelta(days=21)


def test_unknown_gap_keeps_the_old_ephemeral_window():
    assert ephemeral_retention_days(None) == EPHEMERAL_DEFAULT_DAYS


def test_a_daily_feed_keeps_about_its_last_hundred_articles():
    assert ephemeral_retention_days(24) == 100


def test_a_fast_feed_keeps_at_least_the_minimum():
    assert ephemeral_retention_days(0.25) == PRUNE_MIN_DAYS


def test_a_slow_feed_keeps_at_most_the_maximum():
    assert ephemeral_retention_days(30 * 24) == PRUNE_MAX_DAYS
