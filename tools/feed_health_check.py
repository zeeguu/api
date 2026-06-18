#!/usr/bin/env python
"""
Feed Health Check - alerts on individual stale feeds (dead RSS sources).

Emails the report via ZeeguuMailer (the app's own SMTP) when stale feeds are
found; silent otherwise. It used to just print to stdout "for cron to email",
but cron jobs run under run_task.sh which swallows stdout into a log file — and
the host MTA drops mail anyway — so those warnings never reached anyone.

For "is the crawler as a whole alive right now?" see crawler_liveness_check.py.

Usage:
    python -m tools.feed_health_check [--days N] [--verbose]
"""

import argparse
from datetime import datetime, timedelta

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import Feed
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

app = create_app_for_scripts()
app.app_context().push()

DEFAULT_STALE_DAYS = 3


def check_stale_feeds(stale_days: int, verbose: bool = False):
    """Find active feeds that haven't been updated recently."""

    cutoff = datetime.now() - timedelta(days=stale_days)

    stale_feeds = []
    for feed in Feed.query.filter_by(deactivated=0).all():
        if feed.last_crawled_time and feed.last_crawled_time < cutoff:
            days_stale = (datetime.now() - feed.last_crawled_time).days
            stale_feeds.append((feed, days_stale))
        elif feed.last_crawled_time is None:
            stale_feeds.append((feed, None))

    return sorted(stale_feeds, key=lambda x: x[1] if x[1] else 999, reverse=True)


def main():
    parser = argparse.ArgumentParser(description="Check feed health")
    parser.add_argument("--days", type=int, default=DEFAULT_STALE_DAYS,
                        help=f"Days without update to consider stale (default: {DEFAULT_STALE_DAYS})")
    parser.add_argument("--verbose", action="store_true",
                        help="Show all feeds, not just problems")
    args = parser.parse_args()

    stale_feeds = check_stale_feeds(args.days, args.verbose)

    if not stale_feeds:
        print(f"OK: no active feed is more than {args.days} days stale.")
        return

    lines = [f"=== STALE FEEDS (no updates in {args.days}+ days) ===", ""]
    for feed, days in stale_feeds:
        if days is None:
            lines.append(f"  [{feed.language.code}] {feed.title} (id={feed.id}) - NEVER CRAWLED")
        else:
            lines.append(f"  [{feed.language.code}] {feed.title} (id={feed.id}) - {days} days stale")
            lines.append(f"      Last crawled: {feed.last_crawled_time}")
            if feed.url:
                lines.append(f"      URL: {feed.url.as_string()}")
        lines.append("")

    # Print for the run_task log (manual/debug runs) and email the report so it
    # actually reaches a human.
    print("\n".join(lines))
    ZeeguuMailer.send_mail(f"⚠️ Zeeguu: {len(stale_feeds)} stale feed(s) (>{args.days}d)", lines)


if __name__ == "__main__":
    main()
