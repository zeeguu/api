from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn

import zeeguu.core
from zeeguu.core.model.article_topic_map import TopicOriginType
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.topic_rule import TopicRule
from zeeguu.core.model import Article
from zeeguu.core.test.mocking_the_web import (
    URL_CNN_KATHMANDU,
    URL_SPIEGEL_VENEZUELA,
)

session = zeeguu.core.model.db.session


class ArticleTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.article1 = ArticleRule().article
        self.article2 = ArticleRule().article
        self.language = LanguageRule.get_or_create_language("en")

    def test_articles_are_different(self):
        assert self.article1.title != self.article2.title

    def test_article_representation_does_not_error(self):
        assert self.article1.article_info()

    def test_add_topic(self):
        sports = TopicRule.get_or_create_topic(1)
        health_society = TopicRule.get_or_create_topic(5)
        self.article1.add_topic_if_doesnt_exist(
            health_society, session, TopicOriginType.HARDSET
        )
        self.article1.add_topic_if_doesnt_exist(
            sports, session, TopicOriginType.HARDSET
        )
        assert len(self.article1.topics) == 2
        article_topics = [atm.topic for atm in self.article1.topics]
        assert sports in article_topics
        assert health_society in article_topics

    def test_topic_replacement(self):
        health_society = TopicRule.get_or_create_topic(5)
        self.article1.add_topic_if_doesnt_exist(
            health_society, session, TopicOriginType.INFERRED
        )
        article_topics = [atm.topic for atm in self.article1.topics]
        assert len(self.article1.topics) == 1
        assert health_society in article_topics
        assert TopicOriginType.INFERRED == self.article1.topics[0].origin_type

        self.article1.add_or_replace_topic(
            health_society, session, TopicOriginType.HARDSET
        )
        assert len(self.article1.topics) == 1
        assert health_society in article_topics
        assert TopicOriginType.HARDSET == self.article1.topics[0].origin_type

    def test_find_or_create(self):
        self.new_art = Article.find_or_create(session, URL_SPIEGEL_VENEZUELA)
        assert self.new_art.get_fk_difficulty()

    def test_load_article_without_language_information(self):
        art = Article.find_or_create(session, URL_CNN_KATHMANDU)
        assert art
