from unittest import TestCase

from zeeguu_api.tests.api_test_mixin import APITestMixin
import zeeguu
from tests_core_zeeguu.rules.article_rule import ArticleRule

session = zeeguu.db.session


class StarredArticlesTest(APITestMixin, TestCase):
    def setUp(self):
        super(StarredArticlesTest, self).setUp()
        self.article = ArticleRule().article
        self.url = self.article.url

    def test_no_article_is_starred(self):
        articles = self.json_from_api_get('/get_starred_articles')
        assert not articles

# TODO: We still have to test /star_article and /unstar_article ... 