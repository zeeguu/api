# coding=utf-8

from unittest import TestCase

from zeeguu_core_test.test_data.mocking_the_web import spiegel_venezuela_url
from zeeguu_api_test.api_test_mixin import APITestMixin
import urllib.parse


class ArticleTests(APITestMixin, TestCase):

    def setUp(self):
        super(ArticleTests, self).setUp()
        self.url_quoted = urllib.parse.quote_plus(spiegel_venezuela_url)

    def test_article_info_other_way(self):
        result = self.json_from_api_get('/article_id', other_args=dict(url=self.url_quoted))
        assert (result['article_id'])
