#!/usr/bin/env python
"""
Feed Health Check - alerts on individual stale feeds (dead RSS sources).

"Stale" is relative to the feed's own pace: no new article for STALE_GAPS of
its usual gaps, and at least MIN_STALE_DAYS (see zeeguu/core/feed_cadence.py),
so a monthly blog doesn't alert every week. Feeds of languages that are not
being crawled are skipped: they are stale by choice.

Emails the report via ZeeguuMailer (the app's own SMTP) when stale feeds are
found; silent otherwise. It used to just print to stdout "for cron to email",
but cron jobs run under run_task.sh which swallows stdout into a log file — and
the host MTA drops mail anyway — so those warnings never reached anyone.

For "is the crawler as a whole alive right now?" see crawler_liveness_check.py.

Usage:
    python -m tools.feed_health_check
"""

from datetime import datetime

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.crawl_schedule import CRAWL_SCHEDULE
from zeeguu.core.feed_cadence import stale_after
from zeeguu.core.model import Feed
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.operations.task_status import set_summary

app = create_app_for_scripts()
app.app_context().push()

def is_crawled(language_code):
    crawl = CRAWL_SCHEDULE.get(language_code)
    return crawl is not None and bool(crawl.hours)


def check_stale_feeds():
    """Find active feeds that have been quiet for longer than their pace allows."""

    now = datetime.now()
    stale_feeds = []
    for feed in Feed.query.filter_by(deactivated=0).all():
        if not is_crawled(feed.language.code):
            continue
        if feed.last_crawled_time is None:
            stale_feeds.append((feed, None))
        elif now - feed.last_crawled_time > stale_after(feed.typical_gap_hours):
            stale_feeds.append((feed, (now - feed.last_crawled_time).days))

    return sorted(stale_feeds, key=lambda x: x[1] if x[1] else 999, reverse=True)


def main():
    stale_feeds = check_stale_feeds()

    if not stale_feeds:
        print("OK: no active feed is stale for its pace.")
        set_summary("no feed stale")
        return
    set_summary(f"{len(stale_feeds)} feed(s) stale")

    lines = ["=== STALE FEEDS (quiet for 3+ of their usual gaps, and 7+ days) ===", ""]
    for feed, days in stale_feeds:
        if days is None:
            lines.append(f"  [{feed.language.code}] {feed.title} (id={feed.id}) - NEVER CRAWLED")
        else:
            gap = feed.typical_gap_hours
            usual = "unknown" if gap is None else f"{gap / 24:.1f}d"
            lines.append(f"  [{feed.language.code}] {feed.title} (id={feed.id}) - {days} days stale (usual gap: {usual})")
            lines.append(f"      Last crawled: {feed.last_crawled_time}")
            if feed.url:
                lines.append(f"      URL: {feed.url.as_string()}")
        lines.append("")

    # Print for the run_task log (manual/debug runs) and email the report so it
    # actually reaches a human.
    print("\n".join(lines))
    ZeeguuMailer.send_alert(f"⚠️ Zeeguu: {len(stale_feeds)} stale feed(s)", lines)


if __name__ == "__main__":
    main()
