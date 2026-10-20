"""
feedparser parses an item's date into a UTC time.struct_time. The RSS handler
only accepted a datetime and fell back to now(), so every item looked brand
new: the feed's last_crawled_time filter never skipped anything, and articles
got their crawl time as published_time.

Since the dates are real, feed_items filters by them again; it keeps a day's
margin before last_crawled_time for items that show up in a feed late.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import TestCase

import feedparser

from zeeguu.core.model import Feed
from zeeguu.core.feed_handler.rssfeed import RSSFeed

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title>
<item><title>a</title><link>https://example.com/a</link>
  <pubDate>Mon, 19 Oct 2026 19:49:13 +0200</pubDate></item>
<item><title>b</title><link>https://example.com/b</link>
  <updated>2026-10-19T08:00:00Z</updated></item>
<item><title>c</title><link>https://example.com/c</link></item>
</channel></rss>"""


class RssItemDatesTest(TestCase):
    def setUp(self):
        self.feed = RSSFeed("https://example.com/rss", 0)
        self.entries = feedparser.parse(RSS).entries

    def _date(self, entry):
        return self.feed.get_server_time(
            entry.get("published_parsed") or entry.get("updated_parsed")
        )

    def test_the_published_date_is_converted_to_server_time(self):
        assert self._date(self.entries[0]) == datetime(2026, 10, 19, 17, 49, 13)

    def test_updated_is_used_when_there_is_no_published_date(self):
        assert self._date(self.entries[1]) == datetime(2026, 10, 19, 8, 0, 0)

    def test_an_item_without_a_date_is_dated_now(self):
        assert datetime.now() - self._date(self.entries[2]) < timedelta(seconds=5)


class LateItemMarginTest(TestCase):
    """feed_items keeps items up to a day older than last_crawled_time."""

    def _items_kept(self, *hours_before_last_crawl):
        last_crawled = datetime(2026, 10, 19, 10, 30)
        candidates = [
            dict(title=str(h), url=f"https://example.com/{h}", content="", summary="",
                 published_datetime=last_crawled - timedelta(hours=h))
            for h in hours_before_last_crawl
        ]
        feed = Feed.__new__(Feed)
        feed.initializeFeedHandler = lambda: None
        feed.feed_handler = SimpleNamespace(get_feed_articles=lambda: candidates)
        return [int(i["title"]) for i in feed.feed_items(last_crawled)]

    def test_an_item_that_shows_up_late_is_still_crawled(self):
        # Dated 09:30, but only added to the feed after a crawl saw a 10:30 item.
        assert self._items_kept(1) == [1]

    def test_items_older_than_the_margin_are_skipped(self):
        assert self._items_kept(1, 23, 25, 24 * 30) == [1, 23]
