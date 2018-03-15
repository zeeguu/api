# coding=utf-8

from unittest import TestCase

from tests_zeeguu_api.api_test_mixin import APITestMixin
import urllib.parse

URL_1 = "http://www.spiegel.de/politik/deutschland/diesel-fahrverbote-schuld-sind-die-grenzwerte-kolumne-a-1197123.html"


class UserArticleTests(APITestMixin, TestCase):

    def setUp(self):
        super(UserArticleTests, self).setUp()
        self.url_quoted = urllib.parse.quote_plus(URL_1)
        self.url = URL_1

    def test_article_info_other_way(self):
        result = self.json_from_api_get('/user_article', other_args=dict(url=self.url_quoted))
        assert "content" in result
        assert "translations" in result

    def test_article_update(self):
        # Article is not starred initially
        result = self.json_from_api_get('/user_article', other_args=dict(url=self.url_quoted))
        assert (not result['starred'])

        # Make starred
        self.api_post(f'/user_article', formdata=dict(url=self.url, starred='True'))

        # Article should be starred
        result = self.json_from_api_get('/user_article', other_args=dict(url=self.url_quoted))
        assert (result['starred'])

        # Make liked
        self.api_post(f'/user_article', formdata=dict(url=self.url, liked='True'))

        # Article should be both liked and starred
        result = self.json_from_api_get('/user_article', other_args=dict(url=self.url_quoted))
        assert (result['starred'])
        assert (result['liked'])

        # Article un-starred
        self.api_post(f'/user_article', formdata=dict(url=self.url, starred='False'))

        # Article is not starred anymore
        result = self.json_from_api_get('/user_article', other_args=dict(url=self.url_quoted))
        assert (not result['starred'])




