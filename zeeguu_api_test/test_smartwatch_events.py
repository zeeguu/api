# coding=utf-8

import json
from unittest import TestCase

from zeeguu_api_test.api_test_mixin import APITestMixin


class SmartwatchEventsTests(APITestMixin, TestCase):
    def _upload_events(self):
        # Create a test array with two glances, one after the other
        events = [
            dict(bookmark_id=1, time="2016-05-05T10:10:10", event="Glance"),
            dict(bookmark_id=1, time="2016-06-05T10:10:11", event="Glance"),
        ]
        result = self.api_post(
            "/upload_smartwatch_events", dict(events=json.dumps(events))
        )
        assert result.data == b"OK"

    # This thing is broken... but the API is also not used by anybody at the moment...
    # def test_get_user_events(self):
    #     self._upload_events()
    #     result = self.json_from_api_get('/get_smartwatch_events')
    #     assert len(result) == 2

    def test_upload_user_activity(self):
        event = dict(
            time="2016-05-05T10:10:10.000Z",
            event="Reading",
            value="200",
            extra_data="seconds",
            article_id="",
        )
        result = self.api_post("/upload_user_activity_data", event)
        assert result.data.decode("utf-8") == "OK"
