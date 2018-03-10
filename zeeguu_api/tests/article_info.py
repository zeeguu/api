# coding=utf-8

from unittest import TestCase

from zeeguu_api.tests.api_test_mixin import APITestMixin
import urllib.parse

URL_1 = "http://www.spiegel.de/politik/deutschland/diesel-fahrverbote-schuld-sind-die-grenzwerte-kolumne-a-1197123.html"


class ArticleInfoTests(APITestMixin, TestCase):

    def setUp(self):
        super(ArticleInfoTests, self).setUp()
        self.url_encoded = urllib.parse.quote_plus(URL_1)
        print(self.url_encoded)

    def test_article_info_other_way(self):
        url = f'/user_article/{self.url_encoded}'
        result = self.json_from_api_get(url, other_args=dict(with_content=True))
        assert "content" in result
