from unittest import TestCase
import os
os.environ["CONFIG_FILE"] = "testing.cfg"

import json
from zeeguu_api.app import app
from zeeguu.populate import TEST_EMAIL
from zeeguu.populate import TEST_PASS
from zeeguu.populate import create_minimal_test_db

import zeeguu


class APITestMixin(TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.session = self.get_session()
        create_minimal_test_db(zeeguu.db)


    def tearDown(self):
        self.app = None
        self.session = None

    def get_session(self):
        rv = self.app.post('/session/'+TEST_EMAIL, data=dict(
            password=TEST_PASS
        ))
        return rv.data

    def in_session(self, url, other_args=[]):
        url_with_session = url + "?session=" + self.session
        for each in other_args:
            url_with_session += "&" + each
        return url_with_session

    # GET
    # ---
    def api_get(self, test_data, formdata='None', content_type=None):
        return self.app.get(self.in_session(test_data), data = formdata, content_type = content_type)

    def raw_data_from_api_get(self, test_data, formdata='None', content_type=None):
        return self.api_get(test_data, formdata, content_type).data

    def json_from_api_get(self, test_data, formdata='None', content_type=None):
        rv = self.api_get(test_data, formdata, content_type)
        return json.loads(rv.data)

    # POST
    # ----
    def api_post(self, test_data, formdata='None', content_type=None):
        return self.app.post(self.in_session(test_data), data = formdata, content_type = content_type)

    def raw_data_from_api_post(self, test_data, formdata='None', content_type=None):
        return self.app.post(self.in_session(test_data), data = formdata, content_type = content_type).data

    def json_from_api_post(self, test_data, formdata='None', _content_type=None):
        url = self.in_session(test_data)
        print (url + "!!!!")
        rv = self.app.post(url, data = formdata, content_type = _content_type)
        print rv.data
        return json.loads(rv.data)
