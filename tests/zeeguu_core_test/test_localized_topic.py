from unittest import TestCase

import zeeguu_core
from sqlalchemy.orm.exc import NoResultFound

from zeeguu_core.model import Topic, LocalizedTopic, Article, Url
from zeeguu_core_test.model_test_mixin import ModelTestMixIn
from zeeguu_core_test.rules.article_rule import ArticleRule
from zeeguu_core_test.rules.language_rule import LanguageRule
from zeeguu_core_test.rules.url_rule import UrlRule
from zeeguu_core_test.rules.user_rule import UserRule
from zeeguu_core.model.language import Language

session = zeeguu_core.db.session


class LocalizedTopicTest(ModelTestMixIn, TestCase):

    def setUp(self):
        super().setUp()
        self.user = UserRule().user

    def test_topic_matching(self):
        self._localized_topic_keyword_in_url(
            "World", "World", "theguardian.com/world",
            "https://www.theguardian.com/world/2020/jun/06/new-zealand-readers"
        )

    def test_topic_matching_is_case_sensitive(self):
        self._localized_topic_keyword_in_url(
            "Music", "Muziek", "the-Voice",
            "https://www.nu.nl/media/6056161/winnaar-negende-seizoen-van-the-Voice-kids-bekend.html"
        )

    def _localized_topic_keyword_in_url(self, topic: str, localized: str, keyword: str, url: str):
        topic = Topic(topic)
        localized_topic = LocalizedTopic(topic, self.user.learned_language, localized)
        localized_topic.keywords = keyword

        article = ArticleRule().article
        url = Url.find_or_create(self.db.session, url)
        article.url = url

        assert localized_topic.matches_article(article)
