#!/usr/bin/env python

from zeeguu.model import RSSFeed, Url, Language
import zeeguu


def test_feed(url: str):
    feed = RSSFeed.from_url(_feed_url)

    feed_items = feed.feed_items()
    if not feed_items:
        print("Feed seems broken. No items found.")
    else:
        count = len(feed_items)
        print(f"Feed seems healthy: {count} items found. ")

    return feed


RESOURCES_FOLDER = "https://zeeguu.unibe.ch/api/resources/"

_feed_url = input("Feed url:  ")
test_feed = test_feed(_feed_url)

feed_name = input(f"Feed name (Enter for: {test_feed.title}):  ") or test_feed.title
print(f'= {feed_name}')

icon_name = input(
    "Icon name to be found in resources folder (e.g. 20min.png):  ")
print (f'= {icon_name}')

description = input(f'Description (Enter for: {test_feed.description}): ') or test_feed.description
print(f'= {description}')

_language = input("Language code (e.g. en): ")
print(f'= {_language}')

icon_url = Url.find_or_create(zeeguu.db.session, RESOURCES_FOLDER + icon_name)
feed_url = Url.find_or_create(zeeguu.db.session, _feed_url)
language = Language.find_or_create(_language)

rss_feed = RSSFeed.find_or_create(zeeguu.db.session, feed_url, feed_name, description, icon_url, language)

print("Done: ")
print(rss_feed.title)
print(rss_feed.description)
print(rss_feed.language_id)
print(rss_feed.url.as_string())
print(rss_feed.image_url.as_string())
