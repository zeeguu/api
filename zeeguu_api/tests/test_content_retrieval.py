import json
from unittest import TestCase

from zeeguu_api.tests.api_test_mixin import APITestMixin

URL_1 = "http://www.derbund.ch/wirtschaft/unternehmen-und-konjunktur/die-bankenriesen-in-den-bergkantonen/story/26984250"
URL_2 = "http://www.computerbase.de/2015-11/bundestag-parlament-beschliesst-das-ende-vom-routerzwang-erneut/"


class TranslationTests(APITestMixin, TestCase):

    # getting content from url
    def test_content_from_url(self):
        # parameters
        manual_check = False

        form_data = dict(
                        urls=[
                                dict (url=URL_1, id=1),
                                dict (url=URL_2, id=2)],
                        lang_code="de")
        form_data = json.dumps(form_data)

        data = self.json_from_api_post('/get_content_from_url', form_data, "application/json")

        urls = data['contents']
        for url in urls:
            assert url['content'] is not None
            assert url['image'] is not None
            assert url['difficulty'] is not None
            assert url['difficulty']
            if manual_check:
                assert (url['content'])
                assert (url['image'])
