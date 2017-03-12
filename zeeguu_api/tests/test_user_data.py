# coding=utf-8

from unittest import TestCase

from api_test_mixin import APITestMixin


class UserDataTests(APITestMixin, TestCase):

    def test_get_language(self):
        rv = self.api_get('/learned_language')
        assert rv.data == "de"

    def test_set_language(self):
        rv = self.api_post('/learned_language/en')
        rv = self.api_post('/native_language/de')
        assert "OK" in rv.data

        rv = self.api_get('/learned_language')
        assert rv.data== "en"

        rv = self.api_get('/native_language')
        assert rv.data== "de"

    def test_create_user(self):
        form_data = dict(
            username= "gigi",
            password= "lala"
        )
        rv = self.api_post('/add_user/i@i.la',form_data)
        # print rv.data
        assert rv.data > 1

    def test_get_language(self):
        rv = self.api_get('/learned_language')
        assert rv.data == "de"

    def test_get_user_details(self):

        details = self.json_from_api_get('/get_user_details')
        assert details
        assert details["name"]
        assert details["email"]
