# coding=utf-8

from unittest import TestCase
from zeeguu_api_test.api_test_mixin import APITestMixin


class UserLanguagesTest(APITestMixin, TestCase):
    def test_set_language(self):
        learned_language_code_to_set = "de"

        self.api_post("/learned_language/" + learned_language_code_to_set)
        language_code_read = self.json_from_api_get("/user_languages/reading")[0][
            "code"
        ]

        assert language_code_read == learned_language_code_to_set
