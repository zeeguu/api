# coding=utf-8

from unittest import TestCase
from unittest.mock import patch

from zeeguu_api_test.api_test_mixin import APITestMixin


class UserLoginTest(APITestMixin, TestCase):
    @patch(
        "zeeguu_core.account_management.user_account_creation.valid_invite_code",
        return_value=True,
    )
    def test_set_language(self, mock_invite_code):
        EMAIL = "LULU@mir.lu"
        EMAIL_DIFFERENT_CASE = "lulu@mir.lu"
        PASS = "pass"
        USERNAME = "Lulu"

        self.string_from_api_post(
            f"/add_user/{EMAIL}", dict(password=PASS, username=USERNAME)
        )

        session = self.json_from_api_post(
            f"/session/{EMAIL_DIFFERENT_CASE}", dict(password="pass")
        )
        assert int(session)

    @patch(
        "zeeguu_core.account_management.user_account_creation.valid_invite_code",
        return_value=False,
    )
    def test_set_language_without_invite(self, mock_invite_code):
        EMAIL = "LULU@mir.lu"
        EMAIL_DIFFERENT_CASE = "lulu@mir.lu"
        PASS = "pass"
        USERNAME = "Lulu"

        result = self.string_from_api_post(
            f"/add_user/{EMAIL}", dict(password=PASS, username=USERNAME)
        )

        assert "Invitation code is not recognized" in result
