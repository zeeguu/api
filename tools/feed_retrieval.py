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
import datetime
import watchmen

import zeeguu
from zeeguu import model
from zeeguu.model import Url, RSSFeed

LOG_CONTEXT = "FEED RETRIEVAL"

session = zeeguu.db.session

for feed in RSSFeed.query.all():

    for feed_item in feed.feed_items():

        title = feed_item['title']
        url = feed_item['url']

        art = model.Article.find(url)

        if art:
            print(f"Already found in the DB: {art}")
        else:
            try:
                art = watchmen.article_parser.get_article(url)

                word_count = len(art.text.split(" "))

                if word_count < 10:
                    zeeguu.lognprint(f" {LOG_CONTEXT}: Can't find text for: {url}")

                else:
                    from zeeguu.language.difficulty_estimator_factory import DifficultyEstimatorFactory

                    fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
                    fk_difficulty = fk_estimator.estimate_difficulty(art.text, feed.language, None)['normalized']

                    # Create new article and save it to DB
                    new_article = zeeguu.model.Article(
                        Url.find_or_create(session, url),
                        title,
                        ', '.join(art.authors),
                        art.text,
                        fk_difficulty,
                        word_count,
                        datetime.datetime.now(),
                        feed,
                        feed.language
                    )
                    session.add(new_article)
                    session.commit()
                    zeeguu.lognprint()
                    print(f" {LOG_CONTEXT}: Added: {new_article}")
            except Exception as ex:
                zeeguu.lognprint(f" {LOG_CONTEXT}: Failed to create zeeguu.Article from {url}")
                zeeguu.log(str(ex))
