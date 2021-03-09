# coding=utf-8

from unittest import TestCase
from zeeguu_api_test.api_test_mixin import APITestMixin


class UserDataTests(APITestMixin, TestCase):
    def test_set_language(self):
        self.assertEqual("OK", self.string_from_api_post("/learned_language/en"))

        self.assertEqual("OK", self.string_from_api_post("/native_language/de"))

        self.assertEqual("en", self.api_get_string("/learned_language"))

        self.assertEqual("de", self.api_get_string("/native_language"))

    def test_get_user_details(self):
        details = self.json_from_api_get("/get_user_details")

        self.assertIsNotNone(details)
        self.assertIsNotNone(details["name"])
        self.assertIsNotNone(details["email"])
