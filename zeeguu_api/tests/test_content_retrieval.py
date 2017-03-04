import json
from unittest import TestCase

from api_test_mixin import APITestMixin


class TranslationTests(APITestMixin, TestCase):

    # getting content from url
    def test_content_from_url(self):
        # parameters
        manual_check = False

        form_data = dict(
            urls=[dict
                (url="http://www.derbund.ch/wirtschaft/unternehmen-und-konjunktur/die-bankenriesen-in-den-bergkantonen/story/26984250", id=1),
                  dict
                      (url="http://www.computerbase.de/2015-11/bundestag-parlament-beschliesst-das-ende-vom-routerzwang-erneut/", id=2)],
            lang_code="de")

        jsonified = json.dumps(form_data)
        data = self.json_from_api_post('/get_content_from_url', jsonified, "application/json")

        urls = data['contents']
        for url in urls:
            assert url['content'] is not None
            assert url['image'] is not None
            assert url['difficulty'] is not None
            print url['difficulty']
            if manual_check:
                print (url['content'])
                print (url['image'])
