#!/usr/bin/env python

from zeeguu_core.model import RSSFeed, Url, Language, RSSFeedRegistration
import zeeguu_core

session = zeeguu_core.db.session

name = input("Feed name to delete: " )

all_feeds = RSSFeed.query.all()
for feed in all_feeds:
    if feed.title == name:
        print("About to delete... " + name + "with id" + str(feed.id))
        for reg in RSSFeedRegistration.query.all():
            if reg.rss_feed_id == feed.id:
                print("... would also delete also registraion of user " + reg.user.name)
                session.delete(reg)
        agreement = input("Type d to delete: ") == "d"
        if agreement:
            session.delete(feed)
            session.commit()
            print ("Done.")
        else: 
            session.rollback()
            print ("Not deleting")
        
