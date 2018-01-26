#!/usr/bin/env python

from zeeguu.model import RSSFeed, Url, Language
import zeeguu

RESOURCES_FOLDER = "https://zeeguu.unibe.ch/api/resources/"

feed_name = input("Feed name:  ")
icon_name = input("Icon Name With Extension (e.g. 20min.png) (assumes icon already in the /resources folder on the server):  ")
_feed_url = input("Feed url:  ")
description = input("Description: ")
_language = input("Language code (e.g. en): ")

icon_url = Url.find_or_create(zeeguu.db.session, RESOURCES_FOLDER+icon_name)
feed_url = Url.find_or_create(zeeguu.db.session, _feed_url)
language = Language.find_or_create(_language)

rss_feed = RSSFeed.find_or_create(zeeguu.db.session, feed_url, feed_name, description, icon_url, language)

print ("Done: ")
print (rss_feed.title)
print (rss_feed.description)
print (rss_feed.language_id)
print (rss_feed.url.as_string())
print (rss_feed.image_url.as_string())

items = rss_feed.feed_items()
if not items:
    print ("can't find any items in the feed. seems broken.")
else:
    count = len(items)
    print (f"found {count} items in the feed. feed seems healthy")

