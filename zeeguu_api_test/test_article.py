# coding=utf-8

from unittest import TestCase

from zeeguu_api_test.api_test_mixin import APITestMixin
import urllib.parse

URL_1 = "http://www.spiegel.de/politik/deutschland/diesel-fahrverbote-schuld-sind-die-grenzwerte-kolumne-a-1197123.html"


class ArticleTests(APITestMixin, TestCase):

    def setUp(self):
        super(ArticleTests, self).setUp()
        self.url_quoted = urllib.parse.quote_plus(URL_1)
        self.url = URL_1

    def test_article_info_other_way(self):
        result = self.json_from_api_get('/article_id', other_args=dict(url=self.url_quoted))
        assert (result['article_id'])
