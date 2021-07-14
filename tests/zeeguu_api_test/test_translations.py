# coding=utf-8
from unittest import TestCase

from zeeguu_api_test.api_test_mixin import APITestMixin


class TranslationTests(APITestMixin, TestCase):
    def test_minimize_context(self):
        from zeeguu_api.api.translation import minimize_context

        ctx = "Onderhandelaars ChristenUnie praten over positie homo-ouders"
        from_lang_code = "nl"
        word_str = "Onderhandelaars"

        assert minimize_context(ctx, from_lang_code, word_str)
