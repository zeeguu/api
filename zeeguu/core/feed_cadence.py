"""
How often a feed publishes, and what that means for alerting and pruning.

A feed that posts a hundred articles a day and a blog that posts once a month
can't share one staleness threshold or one retention window: three quiet days
is an outage for the first and normal for the second, and 180 days of retention
is 18,000 articles for the first and six for the second. So both decisions are
scaled by feed.typical_gap_hours, the average time between a feed's articles,
which tools/update_feed_typical_gaps.py measures nightly.

A feed whose gap is unknown (NULL: not measured yet) gets the old fixed
thresholds.
"""

from datetime import timedelta

# The gap is measured over this window. Pruning never shortens a window below
# it (PRUNE_MIN_DAYS), so the articles it counts are never pruned away.
GAP_WINDOW_DAYS = 90
# Below this many articles in the window, the time since the oldest of them
# says too little (one article an hour ago is not a feed posting hourly), so
# the gap is taken over the whole window instead: it can only come out slower.
MIN_ARTICLES_FOR_GAP = 3

# A feed is stale once it has been silent for this many of its usual gaps...
STALE_GAPS = 3
# ...but never sooner than this: some feeds post in weekly bursts (a literary
# weekly's Wednesday batch), which the average gap hides. A dead fast feed is
# still found within a week, and an empty language feed within a day by
# feed_delivery_health_check.
MIN_STALE_DAYS = 7

# An ephemeral feed keeps roughly its last PRUNE_KEEP_ARTICLES articles,
# within these bounds.
PRUNE_KEEP_ARTICLES = 100
PRUNE_MIN_DAYS = GAP_WINDOW_DAYS
PRUNE_MAX_DAYS = 540
# Used when the gap is unknown: the fixed window from before (ADR 023).
EPHEMERAL_DEFAULT_DAYS = 180


def typical_gap_hours(article_count, oldest_published, now):
    """Average hours between articles, from the articles a feed published in
    the last GAP_WINDOW_DAYS. Measuring from the oldest of them rather than
    from the window start keeps a feed added last week from looking slow.
    With fewer than MIN_ARTICLES_FOR_GAP articles the feed is slow by
    definition: the window divided by the count (no articles counts as one)."""
    if article_count < MIN_ARTICLES_FOR_GAP or oldest_published is None:
        return GAP_WINDOW_DAYS * 24 / max(article_count, 1)
    span_hours = (now - oldest_published).total_seconds() / 3600
    return max(span_hours, 0) / article_count


def stale_after(gap_hours):
    """How long a feed may go without a new article before it counts as stale."""
    if gap_hours is None:
        return timedelta(days=MIN_STALE_DAYS)
    return max(timedelta(days=MIN_STALE_DAYS), timedelta(hours=STALE_GAPS * gap_hours))


def ephemeral_retention_days(gap_hours):
    """How many days of an ephemeral feed's articles the pruner keeps."""
    if gap_hours is None:
        return EPHEMERAL_DEFAULT_DAYS
    days = PRUNE_KEEP_ARTICLES * gap_hours / 24
    return round(min(PRUNE_MAX_DAYS, max(PRUNE_MIN_DAYS, days)))
