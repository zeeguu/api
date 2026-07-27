#!/usr/bin/env python
"""
Crawler liveness check — a global heartbeat for the whole crawler.

This is deliberately different from feed_health_check.py. That one asks
"which INDIVIDUAL feeds have gone quiet over DAYS?" — good for spotting a single
dead RSS source. This one asks "is the crawler, as a WHOLE, alive RIGHT NOW?":
if NO active feed across any language has advanced in the last N hours, the
crawler itself is down — a wedged /tmp/zeeguu-crawl.lock (see zeeguu/api#653),
a broken deploy, an unreachable DB — and we want to know within hours, not the
~4 days the per-feed/daily check would have taken.

Alerts go out via ZeeguuMailer (the same SMTP path the API already uses for
verification / report emails), NOT via print-to-stdout: cron jobs here run under
run_task.sh, which redirects stdout+stderr into a log file nobody reads — which
is exactly why feed_health_check's warnings have never reached anyone.

Note on the signal: feed.last_crawled_time stores the *publish time* of the
newest article seen for a feed (not the wall-clock crawl time), so MAX() across
all active feeds is "newest article published anywhere." That can legitimately
lag a few hours in quiet overnight periods, hence the generous default window —
a real stall freezes it for days, so detection is still fast.

Usage:
    python -m tools.crawler_liveness_check [--max-age-hours N]
"""
import argparse
from datetime import datetime

from sqlalchemy import func

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db, Feed
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

app = create_app_for_scripts()
app.app_context().push()

# Generous on purpose: last_crawled_time tracks article publish time, which dips
# in quiet news hours. A genuine outage freezes it for days, so 12h still catches
# it fast while avoiding false alarms. Tighten once the real overnight low-water
# mark is known.
DEFAULT_MAX_AGE_HOURS = 12


def newest_crawl_time():
    """Most recent last_crawled_time across all active feeds — the crawler's
    global heartbeat. None if no active feed has ever been crawled."""
    return (
        db.session.query(func.max(Feed.last_crawled_time))
        .filter(Feed.deactivated == 0)
        .scalar()
    )


def main():
    parser = argparse.ArgumentParser(description="Crawler global liveness heartbeat")
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=DEFAULT_MAX_AGE_HOURS,
        help=f"Alert if no active feed has advanced within this many hours (default: {DEFAULT_MAX_AGE_HOURS})",
    )
    args = parser.parse_args()

    newest = newest_crawl_time()
    now = datetime.now()
    age_hours = None if newest is None else (now - newest).total_seconds() / 3600

    if age_hours is not None and age_hours < args.max_age_hours:
        print(f"OK: newest feed crawl was {age_hours:.1f}h ago ({newest:%Y-%m-%d %H:%M}); "
              f"under the {args.max_age_hours}h threshold.")
        return

    # --- stalled: alert via the app's own mailer ---
    if newest is None:
        headline = "No active feed has ever been crawled"
    else:
        headline = f"Newest feed crawl across ALL languages was {age_hours:.1f}h ago"

    subject = "⚠️ Zeeguu crawler appears STALLED"
    body_lines = [
        f"The crawler liveness check failed at {now:%Y-%m-%d %H:%M}.",
        "",
        f"{headline} — over the {args.max_age_hours}h threshold.",
        f"Newest last_crawled_time across active feeds: {newest}",
        "",
        "This points at the crawler itself being down, not just one feed:",
        "  - a wedged crawl holding /tmp/zeeguu-crawl.lock (see zeeguu/api#653),",
        "  - a broken deploy, or",
        "  - the database / a downstream service being unreachable.",
        "",
        "Triage: ssh thor → `docker ps | grep crawler`, check /var/log/zeeguu/crawler/,",
        "and `ps -eo pid,etime,cmd | grep crawl` for a multi-day-old stuck process.",
    ]

    print(f"ALERT: {subject} — {headline} (threshold {args.max_age_hours}h)")
    ZeeguuMailer.send_mail(subject, body_lines)


if __name__ == "__main__":
    main()
