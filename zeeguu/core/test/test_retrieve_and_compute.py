import newspaper

import zeeguu.core
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.feed_rule import FeedRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.content_cleaning.content_cleaner import cleanup_non_content_bits
from zeeguu.core.content_retriever.article_downloader import download_from_feed
from zeeguu.core.content_quality.quality_filter import sufficient_quality
from zeeguu.core.model import Topic, LocalizedTopic

from zeeguu.core.test.mocking_the_web import *


class TestRetrieveAndCompute(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.user = UserRule().user
        self.lan = LanguageRule().de

    def testDifficultyOfFeedItems(self):
        feed = FeedRule().feed1
        download_from_feed(feed, zeeguu.core.model.db.session, 3, False)

        articles = feed.get_articles(limit=2)

        assert len(articles) == 2
        assert articles[0].fk_difficulty

    def testDownloadWithTopic(self):
        feed = FeedRule().feed1
        topic = Topic("Spiegel")
        zeeguu.core.model.db.session.add(topic)
        zeeguu.core.model.db.session.commit()
        loc_topic = LocalizedTopic(topic, self.lan, "spiegelDE", "spiegel")
        zeeguu.core.model.db.session.add(loc_topic)
        zeeguu.core.model.db.session.commit()

        download_from_feed(feed, zeeguu.core.model.db.session, 3, False)

        article = feed.get_articles(limit=2)[0]

        assert topic in article.topics

    def test_sufficient_quality(self):
        art = newspaper.Article(URL_PROPUBLICA_INVESTING)
        art.download()
        art.parse()

        assert sufficient_quality(art)

    def test_new_scientist_overlay(self):
        art = newspaper.Article(URL_NEWSCIENTIST_FISH)
        art.download()
        art.parse()

        is_quality, _ = sufficient_quality(art)
        assert not is_quality

    def test_le_monde_subscription(self):
        art = newspaper.Article(URL_LEMONDE_VOLS_AMERICAINS)
        art.download()
        art.parse()

        is_quality, _ = sufficient_quality(art)
        assert not is_quality

    def test_fragment_removal(self):
        art = newspaper.Article(URL_ONION_US_MILITARY)
        art.download()
        art.parse()

        cleaned_up_text = cleanup_non_content_bits(art.text)
        assert "Advertisement" not in cleaned_up_text
    
    def test_ml_classification(self):
        db_content = mock_readability_call(URL_ML_JP_PAYWALL)

        is_quality, reason = sufficient_quality(db_content)
        assert not is_quality
        assert reason == "ML Prediction was 'Paywalled'."
