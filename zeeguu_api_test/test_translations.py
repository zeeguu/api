# coding=utf-8
from unittest import TestCase
from unittest.mock import patch

from zeeguu_api_test.api_test_mixin import APITestMixin
from zeeguu_api_test.mocks.mock_translator import MockTranslator
from zeeguu_core_test.test_data.mocking_the_web import spiegel_venezuela_url


class TranslationTests(APITestMixin, TestCase):

    def setUp(self):
        super(TranslationTests, self).setUp()

    @patch("zeeguu_api.api.translate_and_bookmark.Translator")
    def test_get_possible_translations(self, mock_bet):
        mock_bet.return_value = MockTranslator({"klein": ["small", "little"], "krassen": ["big"]})

        form_data = dict(
            url=spiegel_venezuela_url,
            context='Die klein Jäger',
            word="klein")
        alternatives = self.json_from_api_post('/get_possible_translations/de/en', form_data)
        first_alternative = alternatives['translations'][0]
        second_alternative = alternatives['translations'][1]

        assert first_alternative is not None
        assert second_alternative is not None
        assert first_alternative["likelihood"] >= second_alternative["likelihood"]

    @patch("zeeguu_api.api.translate_and_bookmark.Translator")
    def test_get_translation_where_gslobe_fails_but_translate_succeeds(self, mock_bet):
        mock_bet.return_value = MockTranslator({"klein": ["small"], "krassen": ["big", "extreme"]})

        form_data = dict(
            url=spiegel_venezuela_url,
            context='Die krassen Jägermeister',
            word="krassen")
        alternatives = self.json_from_api_post('/get_possible_translations/de/en', form_data)

        first_alternative = alternatives['translations'][0]
        assert first_alternative is not None

        second_alternative = alternatives['translations'][1]
        assert second_alternative is not None

    @patch("zeeguu_api.api.translate_and_bookmark.Translator")
    def test_translate_and_bookmark(self, mock_bet):
        mock_bet.return_value = MockTranslator({"Die": ["The"], "kleine": ["small"]})

        form_data = dict(
            url=spiegel_venezuela_url,
            context='Die kleine Jägermeister',
            word="Die")

        bookmark1 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        bookmark2 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)

        assert (bookmark1["bookmark_id"] == bookmark2["bookmark_id"])

        form_data["word"] = "kleine"
        bookmark3 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)

        self.assertTrue(bookmark3['translation'] == 'small')

    def test_minimize_context(self):
        from zeeguu_api.api.translate_and_bookmark import minimize_context
        ctx = "Onderhandelaars ChristenUnie praten over positie homo-ouders"
        from_lang_code = "nl"
        word_str = "Onderhandelaars"

        assert (minimize_context(ctx, from_lang_code, word_str))
