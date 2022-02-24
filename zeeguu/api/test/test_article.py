from unittest import TestCase

from zeeguu.core.test.test_data.mocking_the_web import url_spiegel_venezuela
from zeeguu.api.test.api_test_mixin import APITestMixin


class ArticleTests(APITestMixin, TestCase):
    def setUp(self):
        super(ArticleTests, self).setUp()

    def test_article_info_other_way(self):
        result = self.json_from_api_post(
            "/find_or_create_article", dict(url=url_spiegel_venezuela)
        )
        assert result["article_id"]
