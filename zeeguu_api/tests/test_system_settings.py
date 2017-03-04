# coding=utf-8

from unittest import TestCase

from api_test_mixin import APITestMixin


class SystemSettingsTests(APITestMixin, TestCase):

    def test_available_languages(self):
        rv = self.api_get('/available_languages')
        assert "de" in rv.data

    def test_logout_API(self):
        assert "OK" == self.raw_data_from_api_get('/logout_session')
        rv = self.api_get('/validate')
        assert rv.status== "401 UNAUTHORIZED"



