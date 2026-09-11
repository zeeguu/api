#!/usr/bin/env python
"""
Tag feeds with the country they publish from, and bring their already-indexed
articles into line.

Both halves matter. `feed.country` is what a learner's variety preference is
matched against, but the match happens in Elasticsearch against a field written
when the article was indexed -- so tagging a feed alone leaves every article it
has already published invisible to that preference. Feeds tagged after their
articles were indexed need the second half; feeds tagged before their first
crawl do not.

Re-indexing here is cheap: create_or_update_article passes the existing document
back in, and the embedding is reused rather than regenerated whenever the content
has not changed.

Usage:
  python tools/set_feed_country.py --country FR --feed-ids 66,215,60
  python tools/set_feed_country.py --country FR --feed-ids 66 --execute
  python tools/set_feed_country.py --country BE --feed-ids 91 --execute --reindex-days 60

Dry-run by default: it reports what it would change and touches nothing.
"""
import os

os.environ["PRELOAD_STANZA"] = "false"

import argparse
import time
from datetime import datetime, timedelta

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import Article, Feed
from zeeguu.core.model.db import db

app = create_app_for_scripts()
app.app_context().push()

# How far back to bring the index into line.
#
# Seven days, not thirty: the recommender decays recency on a 1-day scale, so an
# article two weeks old is already unreachable in practice. Each re-index costs a
# row load plus an Elasticsearch get and update, and a daily paper publishes
# enough that the difference between a week and a month is minutes of work for
# articles nobody can reach. Pass --reindex-days 0 to tag without touching the
# index at all.
DEFAULT_REINDEX_DAYS = 7


def say(message):
    # Unbuffered: this runs inside docker compose run, where a buffered stdout
    # turns steady progress into a blank screen.
    print(message, flush=True)


def reindex_with_retry(article_id, attempts=3):
    """
    Re-index one article, retrying a version conflict.

    create_or_update_article reads the document and writes it back, so anything
    else touching the same document in between -- a crawl, a simplification, a
    second copy of this tool -- makes Elasticsearch reject the write with a 409.
    It is a conflict, not a failure: the next read sees the newer document and
    the write lands. Measured on a French backfill, about 2% of articles hit one.
    """
    from elasticsearch.exceptions import ConflictError

    from zeeguu.core.elastic.indexing import create_or_update_article

    for attempt in range(attempts):
        try:
            create_or_update_article(Article.find_by_id(article_id), db.session)
            return
        except ConflictError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2 * (attempt + 1))


def main():
    parser = argparse.ArgumentParser(description="Set the country of one or more feeds")
    parser.add_argument("--country", required=True, help="ISO 3166-1 alpha-2, e.g. FR")
    parser.add_argument("--feed-ids", required=True, help="Comma-separated feed ids")
    parser.add_argument("--reindex-days", type=int, default=DEFAULT_REINDEX_DAYS)
    parser.add_argument("--execute", action="store_true", help="Actually write; otherwise dry-run")
    args = parser.parse_args()

    country = args.country.strip().upper()
    feed_ids = [int(each) for each in args.feed_ids.split(",") if each.strip()]
    since = datetime.now() - timedelta(days=args.reindex_days)
    reindexing = args.reindex_days > 0

    say(
        f"{len(feed_ids)} feed(s) -> {country}, "
        + (f"re-indexing back to {since.date()}" if reindexing else "tagging only")
        + "\n"
    )

    for feed_id in feed_ids:
        # Not Feed.find_by_id: it reports a missing row to Sentry, and a typo in
        # a tool argument is not an incident.
        feed = Feed.query.filter(Feed.id == feed_id).first()
        if feed is None:
            print(f"!! no feed {feed_id}")
            continue

        # Ids only. Article carries `content` and `htmlContent` as mediumtext, so
        # materialising a month of a daily paper as ORM objects is hundreds of
        # megabytes and minutes of silence before the first line of output.
        article_ids = (
            [
                row[0]
                for row in db.session.query(Article.id)
                .filter(Article.feed_id == feed_id)
                .filter(Article.published_time >= since)
                .filter(Article.broken == 0)
                .all()
            ]
            if reindexing
            else []
        )
        say(
            f"{feed_id:>5}  {feed.title[:40]:<40} {feed.country or '--'} -> {country}"
            f"   ({len(article_ids)} articles since {since.date()})"
        )

        if not args.execute:
            continue

        feed.country = country
        db.session.add(feed)
        db.session.commit()

        reindexed, failed = 0, 0
        for i, article_id in enumerate(article_ids, start=1):
            try:
                reindex_with_retry(article_id)
                reindexed += 1
            except Exception as e:
                failed += 1
                if failed <= 3:
                    say(f"       article {article_id}: {e}")
            # One row of a long silence is indistinguishable from a hang.
            if i % 50 == 0:
                say(f"       {i}/{len(article_ids)}...")
            # The content columns are large; holding a month of them is what made
            # the first version look stuck.
            if i % 200 == 0:
                db.session.expunge_all()
        say(f"       re-indexed {reindexed}, failed {failed}")

    if not args.execute:
        print("\nDry run. Re-run with --execute to write.")


if __name__ == "__main__":
    main()
