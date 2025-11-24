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

from sqlalchemy.exc import PendingRollbackError
from time import time

import zeeguu.core

from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.logging import log

from zeeguu.core.content_retriever.article_downloader import download_from_feed
from zeeguu.core.model import Feed, Language
from crawl_summary.crawl_report import CrawlReport

db_session = zeeguu.core.model.db.session


def download_for_feeds(list_of_feeds, crawl_report):

    summary_stream = ""
    counter = 0
    all_feeds_count = len(list_of_feeds)

    for feed in list_of_feeds:
        crawl_report.add_feed(feed)
        if feed.deactivated:
            continue

        counter += 1
        try:
            msg = f">>>>>>>>> {feed.title} ({counter}/{all_feeds_count}) <<<<<<<<<< "  # .encode('utf-8')
            log("")
            log(f"{msg}")

            summary_stream += (
                download_from_feed(
                    feed,
                    zeeguu.core.model.db.session,
                    crawl_report,
                )
                + "\n\n"
            )

        except PendingRollbackError as e:
            db_session.rollback()
            log(
                "Something went wrong and we had to rollback a transaction; following is the full stack trace:"
            )
            traceback.print_exc()
            crawl_report.add_feed_error(feed, str(e))

        except Exception as e:
            traceback.print_exc()
            crawl_report.add_feed_error(feed, str(e))

    log(f"Successfully finished processing {counter} feeds.")
    return summary_stream


def retrieve_articles_for_language(language_code, send_email=False):

    start_time = time()
    language = Language.find(language_code)
    all_language_feeds = (
        Feed.query.filter_by(language_id=language.id).filter_by(deactivated=False).all()
    )
    crawl_report = CrawlReport()
    crawl_report.add_language(language_code)

    summary_stream = download_for_feeds(all_language_feeds, crawl_report)
    if send_email:

        log("sending summary email")

        import datetime

        mailer = ZeeguuMailer(
            f"{language.name} Crawl Summary "
            + datetime.datetime.now().strftime("%H:%M"),
            summary_stream,
            "zeeguu.team@gmail.com",
        )
        mailer.send()
    crawl_report.set_total_time(language.code, round(time() - start_time, 2))
    crawl_report.save_crawl_report()
    return crawl_report


def retrieve_articles_from_all_feeds():
    all_feeds = Feed.query.all()
    crawl_report = CrawlReport()
    download_for_feeds(all_feeds, crawl_report)
    crawl_report.save_crawl_report()


if __name__ == "__main__":
    retrieve_articles_from_all_feeds()
