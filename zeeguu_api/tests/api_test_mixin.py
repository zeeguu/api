from unittest import TestCase
import os
import json

# BEGIN: injecting the desired testing config in the app

os.environ["ZEEGUU_API_CONFIG"] = os.path.expanduser("~/.config/zeeguu/api_testing.cfg")
from zeeguu_api.app import app
# END: Injecting the desired config...

from zeeguu.populate import TEST_EMAIL, create_test_db
from zeeguu.populate import TEST_PASS
from zeeguu.populate import create_minimal_test_db
from zeeguu.model import User


import zeeguu


class APITestMixin(TestCase):

    def setUp(self):
        app.testing = True
        self.app = app.test_client()

        with app.test_request_context():
            if hasattr(self, "maximal_populate"):
                # print ("maximal populate")
                create_test_db(zeeguu.db)
            else:
                create_minimal_test_db(zeeguu.db)

        self.session = self.get_session()
        self.user = User.find(TEST_EMAIL)

    def tearDown(self):
        self.app = None
        self.session = None

    def get_session(self):
        rv = self.app.post('/session/'+TEST_EMAIL, data=dict(
            password=TEST_PASS
        ))
        return rv.data.decode('utf8')

    def in_session(self, url, other_args=None):
        if not other_args:
            other_args = []

        url_with_session = url + "?session=" + self.session
        for each in other_args:
            url_with_session += "&" + each
        return url_with_session

    # GET
    # ---
    def api_get(self, test_data, formdata='None', content_type=None):
        return self.app.get(self.in_session(test_data), data = formdata, content_type = content_type)

    def api_get_string(self, test_data, formdata='None', content_type=None):
        return self.app.get(self.in_session(test_data), data = formdata, content_type = content_type).data.decode('utf-8')


    def raw_data_from_api_get(self, test_data, formdata='None', content_type=None):
        return self.api_get(test_data, formdata, content_type).data

    def json_from_api_get(self, test_data, formdata='None', content_type=None):
        rv = self.api_get(test_data, formdata, content_type)
        return json.loads(rv.data)

    # POST
    # ----
    def api_post(self, test_data, formdata='None', content_type=None):
        return self.app.post(self.in_session(test_data), data = formdata, content_type = content_type)

    def string_from_api_post(self, test_data, formdata='None', content_type=None):
        return self.app.post(self.in_session(test_data), data = formdata, content_type = content_type).data.decode('utf-8')

    def raw_data_from_api_post(self, test_data, formdata='None', content_type=None):
        return self.app.post(self.in_session(test_data), data = formdata, content_type = content_type).data

    def json_from_api_post(self, test_data, formdata='None', _content_type=None):
        url = self.in_session(test_data)
        rv = self.app.post(url, data = formdata, content_type = _content_type)
        return json.loads(rv.data)
