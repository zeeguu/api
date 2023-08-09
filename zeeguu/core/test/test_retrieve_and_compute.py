import newspaper

import zeeguu.core
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.rss_feed_rule import RSSFeedRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.content_cleaning.content_cleaner import cleanup_non_content_bits
from zeeguu.core.content_retriever.article_downloader import download_from_feed
from zeeguu.core.content_quality.quality_filter import sufficient_quality
from zeeguu.core.model import Topic, LocalizedTopic

from zeeguu.core.test.test_data.mocking_the_web import *


class TestRetrieveAndCompute(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.user = UserRule().user
        self.lan = LanguageRule().de

    def testDifficultyOfFeedItems(self):
        feed = RSSFeedRule().feed1
        download_from_feed(feed, zeeguu.core.db.session, 3, False)

        articles = feed.get_articles(limit=2)

        assert len(articles) == 2
        assert articles[0].fk_difficulty

    def testDownloadWithTopic(self):
        feed = RSSFeedRule().feed1
        topic = Topic("Spiegel")
        zeeguu.core.db.session.add(topic)
        zeeguu.core.db.session.commit()
        loc_topic = LocalizedTopic(topic, self.lan, "spiegelDE", "spiegel")
        zeeguu.core.db.session.add(loc_topic)
        zeeguu.core.db.session.commit()

        download_from_feed(feed, zeeguu.core.db.session, 3, False)

        article = feed.get_articles(limit=2)[0]

        assert (topic in article.topics)

    def test_sufficient_quality(self):
        art = newspaper.Article(url_investing_in_index_funds)
        art.download()
        art.parse()

        assert (sufficient_quality(art))

    def test_new_scientist_overlay(self):
        art = newspaper.Article(url_fish_will_be_gone)
        art.download()
        art.parse()

        is_quality, _ = sufficient_quality(art)
        assert (not is_quality)

    def test_le_monde_subscription(self):
        art = newspaper.Article(url_vols_americans)
        art.download()
        art.parse()

        is_quality, _ = sufficient_quality(art)
        assert (not is_quality)

    def test_fragment_removal(self):
        art = newspaper.Article(url_onion_us_military)
        art.download()
        art.parse()

        cleaned_up_text = cleanup_non_content_bits(art.text)
        assert ("Advertisement" not in cleaned_up_text)
