#!/usr/bin/env python

"""

   Script that goes through all the feeds that are
   available in the DB and retrieves the newest articles
   in order to populate the DB with them.

   The DB is populated by saving Article objects in the
   articles table.

   Before this script checking whether there were new items
   in a given feed was done while serving the request for
   items to read. That was too slow.

   To be called from a cron job.

"""
import traceback

import zeeguu_core
from zeeguu_core import log
from zeeguu_core.content_retriever.article_downloader import download_from_feed
from zeeguu_core.model import RSSFeed

session = zeeguu_core.db.session


def retrieve_articles_from_all_feeds():
    counter = 0
    all_feeds = RSSFeed.query.all()
    all_feeds_count = len(all_feeds)
    for feed in all_feeds:
        counter += 1
        try:
            msg = f"*** >>>>>>>>> {feed.title} ({counter}/{all_feeds_count}) <<<<<<<<<< "  # .encode('utf-8')
            log("")
            log(f"{msg}")

            download_from_feed(feed, zeeguu_core.db.session)

        except Exception as e:
            traceback.print_exc()


if __name__ == '__main__':
    retrieve_articles_from_all_feeds()
