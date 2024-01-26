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

import zeeguu.core
from zeeguu.logging import log
from zeeguu.core.content_retriever.article_downloader import download_from_feed
from zeeguu.core.model import Feed, Language

db_session = zeeguu.core.model.db.session


def download_for_feeds(list_of_feeds):
    counter = 0
    all_feeds_count = len(list_of_feeds)
    for feed in list_of_feeds:
        if feed.deactivated:
            continue

        counter += 1
        try:
            msg = f">>>>>>>>> {feed.title} ({counter}/{all_feeds_count}) <<<<<<<<<< "  # .encode('utf-8')
            log("")
            log(f"{msg}")

            download_from_feed(feed, zeeguu.core.model.db.session)

        except:
            traceback.print_exc()


def retrieve_articles_for_language(language_code):

    language = Language.find(language_code)
    all_language_feeds = (
        Feed.query.filter_by(language_id=language.id)
        .filter_by(deactivated=False)
        .all()
    )

    download_for_feeds(all_language_feeds)


def retrieve_articles_from_all_feeds():

    counter = 0
    all_feeds = Feed.query.all()
    download_for_feeds(all_feeds)


if __name__ == "__main__":
    retrieve_articles_from_all_feeds()
