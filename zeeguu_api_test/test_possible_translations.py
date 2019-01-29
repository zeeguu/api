# coding=utf-8
#
from unittest import TestCase
from unittest.mock import patch

from zeeguu_api_test.mocks.mock_translator import MockTranslator
from zeeguu_core_test.testing_data import VERY_EASY_STORY_URL
from zeeguu_api_test.api_test_mixin import APITestMixin


class TestPossibleTranslations(APITestMixin, TestCase):

    @patch("zeeguu_api.api.translate_and_bookmark.Translator")
    def test_get_possible_translations(self, mock_translator):
        mock_translator.return_value = MockTranslator({"schon": ["nice"]})

        translations = self.json_from_api_post('/get_possible_translations/de/en',
                                               dict(context="das ist sehr schon",
                                                    url=VERY_EASY_STORY_URL,
                                                    word="schon",
                                                    title="lala"))
        assert "nice" in str(translations)

    @patch("zeeguu_api.api.translate_and_bookmark.Translator")
    def test_get_possible_translations2(self, mock_translator):
        mock_translator.return_value = MockTranslator({"glatzköpfig": ["gifpökztalg"]})
        translations = self.json_from_api_post('/get_possible_translations/de/en',
                                               dict(context="Da sich nicht eindeutig erkennen lässt, "
                                                            "ob Emojis Männer oder eben doch womöglich "
                                                            "glatzköpfig Frauen darstellen,",
                                                    url=VERY_EASY_STORY_URL,
                                                    word="glatzköpfig",
                                                    title="lala"))

        assert "gifpökztalg" in str(translations)
