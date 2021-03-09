from unittest import TestCase

from zeeguu_core_test.model_test_mixin import ModelTestMixIn

import zeeguu_core
from zeeguu_core_test.rules.article_rule import ArticleRule
from zeeguu_core_test.rules.language_rule import LanguageRule
from zeeguu_core.model import Topic, Article
from zeeguu_core_test.test_data.mocking_the_web import url_plane_crashes, url_formation_professionnelle

session = zeeguu_core.db.session


class ArticleTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.article1 = ArticleRule().article
        self.article2 = ArticleRule().article
        self.language = LanguageRule.get_or_create_language("en")

    def test_articles_are_different(self):
        assert (self.article1.title != self.article2.title)

    def test_article_representation_does_not_error(self):
        assert self.article1.article_info()

    def test_add_topic(self):
        health = Topic("health")
        sports = Topic("sports")
        self.article1.add_topic(health)
        self.article1.add_topic(sports)
        assert len(self.article1.topics) == 2

    def test_find_or_create(self):
        self.new_art = Article.find_or_create(session, url_formation_professionnelle)
        assert (self.new_art.fk_difficulty)

    def test_load_article_without_language_information(self):
        art = Article.find_or_create(session, url_plane_crashes)
        assert (art)
