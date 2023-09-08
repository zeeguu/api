# coding=utf-8

from unittest import TestCase

from zeeguu.api.test.api_test_mixin import APITestMixin

URL_1 = "https://www.faz.net/aktuell/sport/mehr-sport/leichtathletik-deutsche-beim-istaf-mit-bestleistungen-nach-der-wm-19150019.html"


class UserArticlesTests(APITestMixin, TestCase):
    def setUp(self):
        super(UserArticlesTests, self).setUp()

    def test_starred_or_liked(self):
        # No article is starred initially
        result = self.json_from_api_get(f"/user_articles/starred_or_liked")
        assert len(result) == 0

        # Star article
        article_id = self.json_from_api_post(
            "/find_or_create_article", dict(url=URL_1)
        )["id"]
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
