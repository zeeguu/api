#!/usr/bin/env python
"""
Measure how often each feed publishes and store it in feed.typical_gap_hours.

Runs nightly before the stale-feed check and the pruner, which both scale with
it (see zeeguu/core/feed_cadence.py). Counts only crawled originals, not their
simplified children.

Usage:
    python -m tools.update_feed_typical_gaps [--dry-run]
"""

import argparse
from datetime import datetime, timedelta

from sqlalchemy import text

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.feed_cadence import GAP_WINDOW_DAYS, typical_gap_hours
from zeeguu.core.model import db, Feed
from zeeguu.operations.task_status import set_summary

app = create_app_for_scripts()
app.app_context().push()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print, don't store")
    args = parser.parse_args()

    now = datetime.utcnow()
    rows = db.session.execute(
        text(
            """
            SELECT feed_id, COUNT(*), MIN(published_time)
            FROM article
            WHERE feed_id IS NOT NULL
              AND parent_article_id IS NULL
              AND published_time > :since
              AND published_time <= :now
            GROUP BY feed_id
            """
        ),
        {"since": now - timedelta(days=GAP_WINDOW_DAYS), "now": now},
    )
    gaps = {feed_id: typical_gap_hours(n, oldest, now) for feed_id, n, oldest in rows}

    measured = 0
    for feed in Feed.query.all():
        gap = gaps.get(feed.id)
        if gap is not None:
            measured += 1
        if args.dry_run:
            shown = "-" if gap is None else f"{gap:.1f}h"
            print(f"  [{feed.language.code}] {feed.title} (id={feed.id}): {shown}")
        else:
            feed.typical_gap_hours = gap

    summary = f"{measured} feed(s) with a measured gap"
    print(summary)
    if not args.dry_run:
        db.session.commit()
        set_summary(summary)


if __name__ == "__main__":
    main()
