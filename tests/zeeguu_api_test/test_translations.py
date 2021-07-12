# coding=utf-8
from unittest import TestCase

from zeeguu_api_test.api_test_mixin import APITestMixin
from zeeguu_core_test.test_data.mocking_the_web import url_spiegel_venezuela


class TranslationTests(APITestMixin, TestCase):
    def setUp(self):
        super(TranslationTests, self).setUp()
        FROM_LANG_CODE = "de"
        TO_LANG_CODE = "en"
        self.data = {
            "from_lang_code": FROM_LANG_CODE,
            "to_lang_code": TO_LANG_CODE,
            "context": None,
            "url": url_spiegel_venezuela,
            "word": None,
            "title": "",
            "query": None,
        }
        self.api_endpoint = "/get_possible_translations/%s/%s" % (
            FROM_LANG_CODE,
            TO_LANG_CODE,
        )

    def test_minimize_context(self):
        from zeeguu_api.api.translate_and_bookmark import minimize_context

        ctx = "Onderhandelaars ChristenUnie praten over positie homo-ouders"
        from_lang_code = "nl"
        word_str = "Onderhandelaars"

        assert minimize_context(ctx, from_lang_code, word_str)
