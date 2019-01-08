# coding=utf-8
from unittest import TestCase

from zeeguu_api_test.api_test_mixin import APITestMixin
from zeeguu_api_test.test_article import URL_1


class TranslationTests(APITestMixin, TestCase):
    
    def setUp(self):
        super(TranslationTests, self).setUp()

    def test_get_possible_translations(self):
        form_data = dict(
            url=URL_1,
            context='Die klein Jäger',
            word="klein")
        alternatives = self.json_from_api_post('/get_possible_translations/de/en', form_data)
        first_alternative = alternatives['translations'][0]
        second_alternative = alternatives['translations'][1]

        assert first_alternative is not None
        assert second_alternative is not None
        assert first_alternative["likelihood"] >= second_alternative["likelihood"]

    def test_get_translation_where_gslobe_fails_but_translate_succeeds(self):
        form_data = dict(
            url=URL_1,
            context='Die krassen Jägermeister',
            word="krassen")
        alternatives = self.json_from_api_post('/get_possible_translations/de/en', form_data)

        first_alternative = alternatives['translations'][0]
        assert first_alternative is not None

    def test_translate_and_bookmark(self):
        form_data = dict(
            url=URL_1,
            context='Die kleine Jägermeister',
            word="Die")

        bookmark1 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        bookmark2 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        bookmark3 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)

        assert (bookmark1["bookmark_id"] == bookmark2["bookmark_id"] == bookmark3["bookmark_id"])

        form_data["word"] = "kleine"
        bookmark4 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        self.assertTrue(bookmark4['translation'] == 'enielk')

    def test_minimize_context(self):
        from zeeguu_api.api.translate_and_bookmark import minimize_context
        ctx = "Onderhandelaars ChristenUnie praten over positie homo-ouders"
        from_lang_code = "nl"
        word_str = "Onderhandelaars"

        assert (minimize_context(ctx, from_lang_code, word_str))
