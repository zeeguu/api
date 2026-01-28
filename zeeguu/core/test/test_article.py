from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn

import zeeguu.core
from zeeguu.core.model.article_topic_map import TopicOriginType
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.topic_rule import TopicRule

session = zeeguu.core.model.db.session


class ArticleTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.article1 = ArticleRule().article
        self.article2 = ArticleRule().article

    def test_article_topics_and_basics(self):
        # articles are different
        assert self.article1.title != self.article2.title

        # article representation does not error
        assert self.article1.article_info()

        # add topic
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

        # topic replacement
        self.article2.add_topic_if_doesnt_exist(
            health_society, session, TopicOriginType.INFERRED
        )
        article2_topics = [atm.topic for atm in self.article2.topics]
        assert len(self.article2.topics) == 1
        assert health_society in article2_topics
        assert TopicOriginType.INFERRED == self.article2.topics[0].origin_type

        self.article2.add_or_replace_topic(
            health_society, session, TopicOriginType.HARDSET
        )
        assert len(self.article2.topics) == 1
        assert health_society in article2_topics
        assert TopicOriginType.HARDSET == self.article2.topics[0].origin_type
