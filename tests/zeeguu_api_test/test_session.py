# coding=utf-8

from unittest import TestCase
from zeeguu_api_test.api_test_mixin import APITestMixin, TEST_EMAIL

import zeeguu_core
from zeeguu_core.model.unique_code import UniqueCode

WANNABE_UUID = "lulu"
TEST_PASS = "cherrypie"


class SessionTests(APITestMixin, TestCase):
    def setUp(self):
        super().setUp()

        zeeguu_core.app.config["INVITATION_CODES"] = ["test"]

    def test_create_user(self):
        form_data = dict(username="gigi", password="lala", invite_code="test")
        rv = self.api_post("/add_user/i@i.la", form_data)
        assert len(rv.data) > 1

    def test_create_user_returns_400_if_password_not_given(self):
        form_data = dict(username="gigi")
        rv = self.api_post("/add_user/i@i.la", form_data)
        assert rv.status_code == 400

    def test_create_user_returns_400_if_password_too_short(self):
        form_data = dict(username="gigi", password="2sh", invite_code="test")
        rv = self.api_post("/add_user/i@i.la", form_data)
        assert rv.status_code == 400

    def test_reset_password(self):
        code = UniqueCode(TEST_EMAIL)
        zeeguu_core.db.session.add(code)
        zeeguu_core.db.session.commit()

        form_data = dict(code=code, password="updated")
        rv = self.api_post("/reset_password/" + TEST_EMAIL, form_data)
        assert rv.status_code == 200

    def test_reset_password_returns_400_invalid_code(self):
        code = UniqueCode(TEST_EMAIL)
        zeeguu_core.db.session.add(code)
        zeeguu_core.db.session.commit()

        form_data = dict(code="thiswontwork", password="updated")
        rv = self.api_post("/reset_password/" + TEST_EMAIL, form_data)
        assert rv.status_code == 400

    def test_reset_password_returns_400_if_password_too_short(self):
        code = UniqueCode(TEST_EMAIL)
        zeeguu_core.db.session.add(code)
        zeeguu_core.db.session.commit()

        form_data = dict(code=code, password="2sh")
        rv = self.api_post("/reset_password/" + TEST_EMAIL, form_data)
        assert rv.status_code == 400

    def test_reset_password_can_use_new_password(self):
        code = UniqueCode(TEST_EMAIL)
        zeeguu_core.db.session.add(code)
        zeeguu_core.db.session.commit()

        form_data = dict(code=code, password="updated")
        rv = self.api_post("/reset_password/" + TEST_EMAIL, form_data)

        form_data = dict(password="updated")

        rv = self.api_post("/session/" + TEST_EMAIL, form_data)

        assert rv.status_code == 200

    def test_reset_password_cant_use_old_password(self):
        code = UniqueCode(TEST_EMAIL)
        zeeguu_core.db.session.add(code)
        zeeguu_core.db.session.commit()

        form_data = dict(code=code, password="updated")
        rv = self.api_post("/reset_password/" + TEST_EMAIL, form_data)

        form_data = dict(password=TEST_PASS)

        rv = self.api_post("/session/" + TEST_EMAIL, form_data)

        assert rv.status_code == 401

    def test_create_anonymous_user(self):
        post_data = {"uuid": WANNABE_UUID, "password": TEST_PASS, "language_code": "es"}

        new_session_id = self.raw_data_from_api_post("/add_anon_user", post_data)
        assert len(new_session_id) > 0

    def get_anonymous_session(self):
        self.test_create_anonymous_user()
        post_data = {"uuid": WANNABE_UUID, "password": TEST_PASS, "language_code": "es"}
        session_id = self.raw_data_from_api_post("/get_anon_session", post_data)
        assert session_id
