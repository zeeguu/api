# coding=utf-8

from unittest import TestCase

from zeeguu_api.tests.api_test_mixin import APITestMixin
import urllib.parse

URL_1 = "http://www.spiegel.de/politik/deutschland/diesel-fahrverbote-schuld-sind-die-grenzwerte-kolumne-a-1197123.html"


class UserArticleTests(APITestMixin, TestCase):

    def setUp(self):
        super(UserArticleTests, self).setUp()
        self.url = urllib.parse.quote_plus(URL_1)

    def test_article_info_other_way(self):
        url = f'/user_article/{self.url}'
        result = self.json_from_api_get(url, other_args=dict(with_content=True))
        assert "content" in result

    def test_article_update(self):
        # Article is not starred initially
        result = self.json_from_api_get(f'/user_article/{self.url}')
        assert (not result['starred'])

        # Make starred
        self.api_post(f'/user_article/{self.url}', formdata=dict(starred='True'))

        # Article should be starred
        result = self.json_from_api_get(f'/user_article/{self.url}')
        assert (result['starred'])

        # Make liked
        self.api_post(f'/user_article/{self.url}', formdata=dict(liked='True'))

        # Article should be both liked and starred
        result = self.json_from_api_get(f'/user_article/{self.url}')
        assert (result['starred'])
        assert (result['liked'])

        # Article un-starred
        self.api_post(f'/user_article/{self.url}', formdata=dict(starred='False'))

        # Article is not starred anymore
        result = self.json_from_api_get(f'/user_article/{self.url}')
        assert (not result['starred'])




