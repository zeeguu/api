# coding=utf-8

from unittest import TestCase

from api_test_mixin import APITestMixin

WANNABE_UUID = 'lulu'
TEST_PASS = 'cherrypie'


class SessionTests(APITestMixin, TestCase):

    def test_create_user(self):
        form_data = dict(
            username= "gigi",
            password= "lala"
        )
        rv = self.api_post('/add_user/i@i.la',form_data)
        assert rv.data > 1

    def test_create_anonymous_user(self):
        post_data = {
            'uuid': WANNABE_UUID,
            'password': TEST_PASS,
            'language_code': 'es'}

        new_session_id = self.raw_data_from_api_post('/add_anon_user', post_data)
        assert new_session_id > 0

    def get_anonymous_session(self):
        self.test_create_anonymous_user()
        post_data = {
            'uuid': WANNABE_UUID,
            'password': TEST_PASS,
            'language_code': 'es'
        }
        session_id = self.raw_data_from_api_post('/get_anon_session', post_data)
        assert session_id

