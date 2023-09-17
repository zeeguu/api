#!/usr/bin/env python

from zeeguu.core.model import RSSFeed
import zeeguu.core

db_session = zeeguu.core.model.db.session

name = input("Feed name: ")

all_feeds = RSSFeed.query.all()
for feed in all_feeds:
    if feed.title == name:

        print(feed.title)
        print(feed.description)
        print(feed.language.code)
        print(feed.url.as_string())
        print(feed.image_url.as_string())
