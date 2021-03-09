# coding=utf-8

from unittest import TestCase

from zeeguu_api_test.api_test_mixin import APITestMixin

URL_1 = "http://www.spiegel.de/politik/deutschland/diesel-fahrverbote-schuld-sind-die-grenzwerte-kolumne-a-1197123.html"


class UserArticlesTests(APITestMixin, TestCase):
    def setUp(self):
        super(UserArticlesTests, self).setUp()
        self.url = URL_1

    def test_starred_or_liked(self):
        # No article is starred initially
        result = self.json_from_api_get(f"/user_articles/starred_or_liked")
        assert len(result) == 0

        # Star article
        article_id = self.json_from_api_get(
            "/article_id", other_args=dict(url=self.url)
        )["article_id"]
        self.api_post(
            f"/user_article", formdata=dict(starred="True", article_id=article_id)
        )

        # One article is starred eventually
        result = self.json_from_api_get(f"/user_articles/starred_or_liked")
        assert len(result) == 1

        # Like article
        self.api_post(
            f"/user_article", formdata=dict(liked="True", article_id=article_id)
        )

        # Still one article is returned
        result = self.json_from_api_get(f"/user_articles/starred_or_liked")
        assert len(result) == 1
