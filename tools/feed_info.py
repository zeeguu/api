#!/usr/bin/python

from zeeguu.model import RSSFeed, Url, Language, RSSFeedRegistration
import zeeguu

session = zeeguu.db.session

name = input("Feed name: " )

all_feeds = RSSFeed.query.all()
for feed in all_feeds:
    if feed.title == name:

        print (feed.title)
        print (feed.description)
        print (feed.language_id)
        print (feed.url.as_string())
        print (feed.image_url.as_string())

        for reg in RSSFeedRegistration.query.all():
            if reg.rss_feed_id == feed.id:
                print("... registraion by user " + reg.user.name)
        
