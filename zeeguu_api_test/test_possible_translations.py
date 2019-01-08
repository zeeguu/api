# coding=utf-8
#
from unittest import TestCase

from zeeguu_core_test.testing_data import VERY_EASY_STORY_URL
from zeeguu_api_test.api_test_mixin import APITestMixin


class Test(APITestMixin, TestCase):

    def test_get_possible_translations(self):
        translations = self.json_from_api_post('/get_possible_translations/de/en',
                                               dict(context="das ist sehr schon", url=VERY_EASY_STORY_URL, word="schon", title="lala"))
        assert "nohcs" in str(translations)

    def test_get_possible_translations2(self):
        translations = self.json_from_api_post('/get_possible_translations/de/en',
                                               dict(context="Da sich nicht eindeutig erkennen lässt, "
                                                            "ob Emojis Männer oder eben doch womöglich "
                                                            "glatzköpfig Frauen darstellen,",
                                                    url=VERY_EASY_STORY_URL, word="glatzköpfig", title="lala"))

        assert "gifpökztalg" in str(translations)
