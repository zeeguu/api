#!/usr/bin/env python
"""
Feed Health Check - alerts on stale or broken feeds.

Prints warnings to stdout if issues found (for cron to email).
Silent if everything is OK.

Usage:
    python -m tools.feed_health_check [--days N] [--verbose]
"""

import argparse
from datetime import datetime, timedelta

from zeeguu.api.app import create_app
from zeeguu.core.model import Feed

app = create_app()
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

    if stale_feeds:
        print(f"=== STALE FEEDS (no updates in {args.days}+ days) ===\n")
        for feed, days in stale_feeds:
            if days is None:
                print(f"  [{feed.language.code}] {feed.title} (id={feed.id}) - NEVER CRAWLED")
            else:
                print(f"  [{feed.language.code}] {feed.title} (id={feed.id}) - {days} days stale")
                print(f"      Last crawled: {feed.last_crawled_time}")
                if feed.url:
                    print(f"      URL: {feed.url.as_string()}")
            print()


if __name__ == "__main__":
    main()
