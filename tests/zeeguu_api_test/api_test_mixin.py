# import warnings
# warnings.filterwarnings("ignore", category=DeprecationWarning)

from unittest import TestCase
import json

import requests_mock
import zeeguu_core

from zeeguu_core_test.test_data.mocking_the_web import mock_requests_get

from unittest.mock import patch

from zeeguu_api.app import app

TEST_PASS = "test"
TEST_EMAIL = "i@mir.lu"
TEST_USER = "test_user"

test_user_data = dict(password=TEST_PASS, username=TEST_USER)

from zeeguu_core.model import User


class APITestMixin(TestCase):
    @patch(
        "zeeguu_core.account_management.user_account_creation.valid_invite_code",
        return_value=True,
    )
    def setUp(self, mock_invite_code):
        # idea from here:
        # https: // docs.pytest.org / en / latest / example / simple.html  # detect-if-running-from-within-a-pytest-run
        # allows the api translate_and_Bookmark to know that it's being called from the unit test
        # and use the reverse translator instead of the real translators

        app.testing = True
        self.app = app.test_client()
        zeeguu_core.db.create_all()

        response = self.app.post(f"/add_user/{TEST_EMAIL}", data=test_user_data)

        self.session = str(int(response.data))
        self.user = User.find(TEST_EMAIL)

    def tearDown(self):
        super(APITestMixin, self).tearDown()

        # sometimes the tearDown freezes on drop_all
        # and it seems that it's because there's still
        # a session open somewhere. Better call first:
        zeeguu_core.db.session.close()
        zeeguu_core.db.drop_all()

    def run(self, result=None):

        # For the unit tests we use several HTML documents
        # that are stored locally so we don't have to download
        # them for every test
        # To do this we mock requests.get
        with requests_mock.Mocker() as m:
            mock_requests_get(m)
            super(APITestMixin, self).run(result)

    def in_session(self, url, other_args=None):
        if not other_args:
            other_args = {}

        url_with_session = url + "?session=" + self.session
        for key, value in other_args.items():
            url_with_session += f"&{key}={value}"
        return url_with_session

    # GET
    # ---
    def api_get(self, test_data, formdata="None", content_type=None, other_args=None):
        return self.app.get(
            self.in_session(test_data, other_args=other_args),
            data=formdata,
            content_type=content_type,
        )

    def api_get_string(
        self, test_data, formdata="None", content_type=None, other_args=None
    ):
        return self.app.get(
            self.in_session(test_data, other_args=other_args),
            data=formdata,
            content_type=content_type,
        ).data.decode("utf-8")

    def raw_data_from_api_get(
        self, test_data, formdata="None", content_type=None, other_args=None
    ):
        return self.api_get(
            test_data, formdata, content_type, other_args=other_args
        ).data

    def json_from_api_get(
        self, test_data, formdata="None", content_type=None, other_args=None
    ):
        rv = self.api_get(test_data, formdata, content_type, other_args=other_args)
        return json.loads(rv.data)

    # POST
    # ----
    def api_post(self, test_data, formdata="None", content_type=None, other_args=None):
        return self.app.post(
            self.in_session(test_data, other_args=other_args),
            data=formdata,
            content_type=content_type,
        )

    def string_from_api_post(
        self, test_data, formdata="None", content_type=None, other_args=None
    ):
        return self.app.post(
            self.in_session(test_data, other_args=other_args),
            data=formdata,
            content_type=content_type,
        ).data.decode("utf-8")

    def raw_data_from_api_post(
        self, test_data, formdata="None", content_type=None, other_args=None
    ):
        return self.app.post(
            self.in_session(test_data, other_args=other_args),
            data=formdata,
            content_type=content_type,
        ).data

    def json_from_api_post(
        self, test_data, formdata="None", _content_type=None, other_args=None
    ):
        url = self.in_session(test_data, other_args=other_args)
        rv = self.app.post(url, data=formdata, content_type=_content_type)
        return json.loads(rv.data)
