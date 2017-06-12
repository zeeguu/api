from unittest import TestCase

from zeeguu_api.tests.api_test_mixin import APITestMixin


class StarredArticlesTest(APITestMixin, TestCase):
    def test_articles_can_be_starred(self):
        self.raw_data_from_api_post('/star_article', dict(url="http://mir.lu", title="test", language_id="en"))
        self.raw_data_from_api_post('/star_article', dict(url="http://mir.lu", title="test", language_id="en"))
        articles = self.json_from_api_get('/get_starred_articles')
        self.assertEqual(1, len(articles))

    def test_articles_can_be_unstarred(self):
        self.raw_data_from_api_post('/star_article', dict(url="http://mir.lu", title="test", language_id="en"))
        self.raw_data_from_api_post('/unstar_article', dict(url="http://mir.lu"))
        articles = self.json_from_api_get('/get_starred_articles')
        self.assertEqual(0, len(articles))
