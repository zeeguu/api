import json
from unittest import TestCase

from zeeguu_api.app import app


class MiniTest(TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.session = self.get_session()

    def test_empty_db(self):
        rv = self.app.get('/available_languages')
        print rv

    def test_get_language(self):
        rv = self.api_get('/learned_language')
        print rv.data
        assert rv.data == "de"

    def test_upload_events(self):
        # Create a test array with two glances, one after the other
        events = [
            dict(
                bookmark_id=1,
                time="2016-05-05T10:10:10",
                event="Glance"
            ),
            dict(
                bookmark_id=1,
                time="2016-06-05T10:10:11",
                event="Glance"
            )
        ]
        result = self.api_post('/upload_smartwatch_events', dict(events=json.dumps(events)))
        assert (result.data == "OK")



    def in_session(self, url, other_args=[]):
        url_with_session = url + "?session=" + self.session
        for each in other_args:
            url_with_session += "&" + each
        return url_with_session

    def get_session(self):
        rv = self.app.post('/session/'+"i@mir.lu", data=dict(
            password="test"))
        return rv.data

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
        rv = self.app.post(url, data = formdata, content_type = _content_type)
        return json.loads(rv.data)
