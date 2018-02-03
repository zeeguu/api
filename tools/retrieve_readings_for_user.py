#!/usr/bin/env python
import datetime
import watchmen

import zeeguu
from zeeguu import model
from zeeguu.model import Url, RSSFeed

print(" ")
session = zeeguu.db.session

feeds = RSSFeed.query.all()

for feed in feeds:
    print(f"{feed}\n")

    feed_items = feed.feed_items()

    for feed_item in feed_items:

        title = feed_item['title']

        url = feed_item['url']
        print(f" -{url}")

        art = model.Article.find(url)

        if art:
            print(f"Already found: {art}")

        else:
            try:
                art = watchmen.article_parser.get_article(url)
                # print(art.text)

                word_count = len(art.text.split(" "))

                if word_count < 10:
                    print("?? seems like we don't actually have text here?")
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
                    print(f"Added: {new_article}")
            except:
                print (" -- something went wrong")
