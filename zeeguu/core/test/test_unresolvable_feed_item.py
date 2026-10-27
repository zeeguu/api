"""
A feed item whose URL can't be resolved must not abort the rest of the feed.

lespresso pins an item linking to its magazine app (paperlit://openlatestissue)
at the top of its RSS. Resolving it raised, and the crawler gave up on the feed
at that first item on every crawl, so nothing new was stored for days.
"""
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch

import requests

import zeeguu.core
from zeeguu.core.content_retriever import article_downloader
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.feed_rule import FeedRule
from zeeguu.operations.crawler.crawl_report import CrawlReport

session = zeeguu.core.model.db.session


class UnresolvableFeedItemTest(ModelTestMixIn, TestCase):
    def test_an_unresolvable_item_is_skipped_not_fatal(self):
        feed = FeedRule().feed
        crawl_report = CrawlReport()
        crawl_report.add_feed(feed)
        now = datetime.now()
        items = [
            {
                "url": url,
                "title": url,
                "summary": "",
                "published_datetime": now - timedelta(minutes=i),
            }
            for i, url in enumerate(
                ["paperlit://openlatestissue", "https://example.com/works"]
            )
        ]
        article = ArticleRule().article

        def resolve(url):
            if not url.startswith("http"):
                raise requests.exceptions.InvalidSchema(f"No connection adapters for {url}")
            return url

        with patch.object(feed, "feed_items", return_value=items), patch.object(
            article_downloader, "_url_after_redirects", side_effect=resolve
        ), patch.object(
            article_downloader, "download_feed_item", return_value=article
        ):
            summary = article_downloader.download_from_feed(
                feed, session, crawl_report, save_in_elastic=False
            )

        assert summary.startswith("1 new articles")
