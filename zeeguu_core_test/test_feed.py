from datetime import datetime, timedelta
from unittest import TestCase

from zeeguu_core_test.model_test_mixin import ModelTestMixIn

from zeeguu_core_test.rules.rss_feed_rule import RSSFeedRule
from zeeguu_core.content_retriever.article_downloader import download_from_feed


class FeedTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()

        self.spiegel = RSSFeedRule().feed1
        download_from_feed(self.spiegel, self.db.session, 3, False)

    def test_feed_items(self):
        assert len(self.spiegel.get_articles()) == 3
        assert len(self.spiegel.get_articles(limit=2)) == 2

    def test_after_date_works(self):
        tomorrow = datetime.now() + timedelta(days=1)
        assert not self.spiegel.get_articles(after_date=tomorrow)

    def test_article_ordering(self):
        ordered_by_difficulty = self.spiegel.get_articles(easiest_first=True)
        assert ordered_by_difficulty[0].fk_difficulty <= ordered_by_difficulty[1].fk_difficulty

        ordered_by_time = self.spiegel.get_articles(most_recent_first =True)
        assert ordered_by_time [0] . published_time >= ordered_by_time [1] . published_time


