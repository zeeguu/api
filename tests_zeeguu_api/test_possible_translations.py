# coding=utf-8
#
from unittest import TestCase

from tests_zeeguu_api.api_test_mixin import APITestMixin


class Test(APITestMixin, TestCase):

    def test_get_possible_translations(self):
        translations = self.json_from_api_post('/get_possible_translations/de/en',
                                               dict(context="das ist sehr schon", url="lalal.is", word="schon", title="lala"))
        assert "beautiful" in str(translations)

    def test_get_possible_translations2(self):
        translations = self.json_from_api_post('/get_possible_translations/de/en',
                                               dict(context="Da sich nicht eindeutig erkennen lässt, "
                                                            "ob Emojis Männer oder eben doch womöglich "
                                                            "glatzköpfig Frauen darstellen,",
                                                    url="lalal.is", word="glatzköpfig", title="lala"))

        assert "bald" in str(translations)
