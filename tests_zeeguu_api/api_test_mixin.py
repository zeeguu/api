from unittest import TestCase
import json

import zeeguu
# This must be set before any of the other Zeeguu / API code
# is imported. Especially the translate API requires it.  
zeeguu._in_unit_tests = True

from zeeguu_api.app import app

from zeeguu.populate import TEST_EMAIL
from zeeguu.populate import TEST_PASS
from zeeguu.populate import create_minimal_test_db
from zeeguu.model import User


class APITestMixin(TestCase):

    def setUp(self):
        # idea from here:
        # https: // docs.pytest.org / en / latest / example / simple.html  # detect-if-running-from-within-a-pytest-run
        # allows the api translate_and_Bookmark to know that it's being called from the unit test
        # and use the reverse translator instead of the real translators

        app.testing = True
        self.app = app.test_client()

        with app.test_request_context():
            create_minimal_test_db(zeeguu.db)

        self.session = self.get_session()
        self.user = User.find(TEST_EMAIL)

    def tearDown(self):
        self.app = None
        self.session = None

    def get_session(self):
        rv = self.app.post('/session/' + TEST_EMAIL, data=dict(
            password=TEST_PASS
        ))
        return rv.data.decode('utf8')

    def in_session(self, url, other_args=None):
        if not other_args:
            other_args = {}

        url_with_session = url + "?session=" + self.session
        for key, value in other_args.items():
            url_with_session += f"&{key}={value}"
        return url_with_session

    # GET
    # ---
    def api_get(self, test_data, formdata='None', content_type=None, other_args=None):
        return self.app.get(self.in_session(test_data, other_args=other_args), data=formdata, content_type=content_type)

    def api_get_string(self, test_data, formdata='None', content_type=None, other_args=None):
        return self.app.get(self.in_session(test_data, other_args=other_args), data=formdata,
                            content_type=content_type).data.decode('utf-8')

    def raw_data_from_api_get(self, test_data, formdata='None', content_type=None, other_args=None):
        return self.api_get(test_data, formdata, content_type, other_args=other_args).data

    def json_from_api_get(self, test_data, formdata='None', content_type=None, other_args=None):
        rv = self.api_get(test_data, formdata, content_type, other_args=other_args)
        return json.loads(rv.data)

    # POST
    # ----
    def api_post(self, test_data, formdata='None', content_type=None, other_args=None):
        return self.app.post(self.in_session(test_data, other_args=other_args), data=formdata,
                             content_type=content_type)

    def string_from_api_post(self, test_data, formdata='None', content_type=None, other_args=None):
        return self.app.post(self.in_session(test_data, other_args=other_args), data=formdata,
                             content_type=content_type).data.decode('utf-8')

    def raw_data_from_api_post(self, test_data, formdata='None', content_type=None, other_args=None):
        return self.app.post(self.in_session(test_data, other_args=other_args), data=formdata,
                             content_type=content_type).data

    def json_from_api_post(self, test_data, formdata='None', _content_type=None, other_args=None):
        url = self.in_session(test_data, other_args=other_args)
        rv = self.app.post(url, data=formdata, content_type=_content_type)
        return json.loads(rv.data)
