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
from datetime import datetime, timedelta

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import Article, Feed
from zeeguu.core.model.db import db

app = create_app_for_scripts()
app.app_context().push()

# How far back to bring the index into line. The feed only ever shows recent
# articles, so re-indexing the whole archive would cost a lot to change nothing
# anyone can see.
DEFAULT_REINDEX_DAYS = 30


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

    for feed_id in feed_ids:
        # Not Feed.find_by_id: it reports a missing row to Sentry, and a typo in
        # a tool argument is not an incident.
        feed = Feed.query.filter(Feed.id == feed_id).first()
        if feed is None:
            print(f"!! no feed {feed_id}")
            continue

        articles = (
            Article.query.filter(Article.feed_id == feed_id)
            .filter(Article.published_time >= since)
            .filter(Article.broken == 0)
            .all()
        )
        print(
            f"{feed_id:>5}  {feed.title[:40]:<40} {feed.country or '--'} -> {country}"
            f"   ({len(articles)} articles since {since.date()})"
        )

        if not args.execute:
            continue

        feed.country = country
        db.session.add(feed)
        db.session.commit()

        # Imported here so a dry run never pays for the Elasticsearch client.
        from zeeguu.core.elastic.indexing import create_or_update_article

        reindexed, failed = 0, 0
        for article in articles:
            try:
                create_or_update_article(article, db.session)
                reindexed += 1
            except Exception as e:
                failed += 1
                print(f"       article {article.id}: {e}")
        print(f"       re-indexed {reindexed}, failed {failed}")

    if not args.execute:
        print("\nDry run. Re-run with --execute to write.")


if __name__ == "__main__":
    main()
