import newspaper

import zeeguu.core
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.feed_rule import FeedRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.topic_rule import TopicRule
from zeeguu.core.model.url_keyword import UrlKeyword
from zeeguu.core.content_cleaning.content_cleaner import cleanup_non_content_bits
from zeeguu.core.content_retriever.article_downloader import download_from_feed
from zeeguu.core.content_quality.quality_filter import (
    sufficient_quality,
    LowQualityTypes,
)
from tools.crawl_summary.crawl_report import CrawlReport

from zeeguu.core.test.mocking_the_web import *


class TestRetrieveAndCompute(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.user = UserRule().user
        self.lan = LanguageRule().de

    def test_difficulty_of_feed_items(self):
        feed = FeedRule().feed1
        crawl_report = CrawlReport()
        crawl_report.add_feed(feed)
        download_from_feed(feed, zeeguu.core.model.db.session, crawl_report, 3, False)

        articles = feed.get_articles(limit=2)

        assert len(articles) == 2
        assert articles[0].get_fk_difficulty()

    def test_download_with_topic(self):
        ## Check if topic associated with the keyword is correctly added.
        feed = FeedRule().feed1
        topic = TopicRule.get_or_create_topic(7)
        url_keyword = UrlKeyword.find_or_create(
            zeeguu.core.model.db.session, "politik", self.lan, topic
        )
        crawl_report = CrawlReport()
        crawl_report.add_feed(feed)
        download_from_feed(feed, zeeguu.core.model.db.session, crawl_report, 3, False)

        article = feed.get_articles(limit=2)[0]
        # http://www.spiegel.de/politik/ausland/venezuela-militaer-unterstuetzt-nicolas-maduro-im-machtkampf-gegen-juan-guaido-a-1249616.html
        #
        #
        assert url_keyword in [aukm.url_keyword for aukm in article.url_keywords]
        assert topic in [atm.topic for atm in article.topics]

    def test_sufficient_quality(self):
        art = newspaper.Article(URL_PROPUBLICA_INVESTING)
        art.download()
        art.parse()

        assert sufficient_quality(art)[0]

    def test_new_scientist_overlay(self):
        art = newspaper.Article(URL_NEWSCIENTIST_FISH)
        art.download()
        art.parse()

        is_quality, _, _ = sufficient_quality(art)
        assert not is_quality

    def test_le_monde_subscription(self):
        art = newspaper.Article(URL_LEMONDE_VOLS_AMERICAINS)
        art.download()
        art.parse()

        is_quality, _, _ = sufficient_quality(art)
        assert not is_quality

    def test_fragment_removal(self):
        art = newspaper.Article(URL_ONION_US_MILITARY)
        art.download()
        art.parse()

        cleaned_up_text = cleanup_non_content_bits(art.text)
        assert "Advertisement" not in cleaned_up_text

    def test_ml_classification(self):
        db_content = mock_readability_call(URL_ML_JP_PAYWALL)

        is_quality, reason, code = sufficient_quality(db_content)
        assert not is_quality
        assert reason == "ML Prediction was 'Paywalled'."
        assert code == LowQualityTypes.ML_PREDICTION
