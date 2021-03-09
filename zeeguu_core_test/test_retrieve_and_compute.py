import newspaper

import zeeguu_core
from zeeguu_core_test.model_test_mixin import ModelTestMixIn
from zeeguu_core_test.rules.language_rule import LanguageRule
from zeeguu_core_test.rules.rss_feed_rule import RSSFeedRule
from zeeguu_core_test.rules.user_rule import UserRule
from zeeguu_core.content_retriever.content_cleaner import cleanup_non_content_bits
from zeeguu_core.content_retriever.article_downloader import download_from_feed, strip_article_title_word
from zeeguu_core.content_retriever.quality_filter import sufficient_quality
from zeeguu_core.model import Topic, LocalizedTopic, ArticleWord

from zeeguu_core_test.test_data.mocking_the_web import *


class TestRetrieveAndCompute(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.user = UserRule().user
        self.lan = LanguageRule().de

    def testDifficultyOfFeedItems(self):
        feed = RSSFeedRule().feed1
        download_from_feed(feed, zeeguu_core.db.session, 3, False)

        articles = feed.get_articles(limit=2)

        assert len(articles) == 2
        assert articles[0].fk_difficulty

    def testDownloadWithTopic(self):
        feed = RSSFeedRule().feed1
        topic = Topic("Spiegel")
        zeeguu_core.db.session.add(topic)
        zeeguu_core.db.session.commit()
        loc_topic = LocalizedTopic(topic, self.lan, "spiegelDE", "spiegel")
        zeeguu_core.db.session.add(loc_topic)
        zeeguu_core.db.session.commit()

        download_from_feed(feed, zeeguu_core.db.session, 3, False )

        article = feed.get_articles(limit=2)[0]

        assert (topic in article.topics)

    def testDownloadWithWords(self):
        feed = RSSFeedRule().feed1

        download_from_feed(feed, zeeguu_core.db.session, 3, False)

        article = feed.get_articles(limit=2)[0]

        # Try two words, as one might be filtered out
        word = strip_article_title_word(article.title.split()[0])
        article_word = ArticleWord.find_by_word(word)

        if word in ['www', ''] or word.isdigit() or len(word) < 3 or len(word) > 25:
            assert (article_word is None)
        else:
            assert (article in article_word.articles)

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
