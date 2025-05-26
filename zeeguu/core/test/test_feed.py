from datetime import datetime, timedelta
from unittest import TestCase

from zeeguu.core.model.db import db
from zeeguu.core.test.model_test_mixin import ModelTestMixIn

from zeeguu.core.test.rules.feed_rule import FeedRule
from zeeguu.core.content_retriever.article_downloader import download_from_feed
from zeeguu.core.feed_handler import FEED_TYPE
from tools.crawl_summary.crawl_report import CrawlReport


class FeedTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.crawl_report = CrawlReport()
        self.spiegel = FeedRule().feed1
        self.newspaper_da = FeedRule().feed_newspaper_da
        self.crawl_report.add_feed(self.spiegel)
        self.crawl_report.add_feed(self.newspaper_da)
        download_from_feed(self.spiegel, db.session, self.crawl_report, 3, False)
        download_from_feed(self.newspaper_da, db.session, self.crawl_report, 3, False)

    def test_feed_items(self):
        assert len(self.spiegel.get_articles()) == 2
        assert len(self.spiegel.get_articles(limit=2)) == 2

    def test_feed_newspaper(self):
        print("ID : ", self.newspaper_da.id)
        assert len(self.newspaper_da.get_articles()) > 0
        assert len(self.newspaper_da.get_articles(limit=2)) == 2

    def test_feed_type(self):
        assert self.spiegel.feed_type == FEED_TYPE["rss"]
        assert self.newspaper_da.feed_type == FEED_TYPE["newspaper"]

    def test_after_date_works(self):
        tomorrow = datetime.now() + timedelta(days=1)
        assert not self.spiegel.get_articles(after_date=tomorrow)

    def test_article_ordering(self):
        ordered_by_difficulty = self.spiegel.get_articles(easiest_first=True)
        print(self.spiegel.get_articles(easiest_first=True))
        assert (
            ordered_by_difficulty[0].get_fk_difficulty()
            <= ordered_by_difficulty[1].get_fk_difficulty()
        )

        ordered_by_time = self.spiegel.get_articles(most_recent_first=True)
        assert ordered_by_time[0].published_time >= ordered_by_time[1].published_time
