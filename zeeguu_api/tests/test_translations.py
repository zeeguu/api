# coding=utf-8
from unittest import TestCase

from zeeguu_api.tests.api_test_mixin import APITestMixin


class TranslationTests(APITestMixin, TestCase):

    def test_get_possible_translations(self):
        form_data = dict(
            url='http://mir.lu',
            context='Die klein Jäger',
            word="klein")
        alternatives = self.json_from_api_post('/get_possible_translations/de/en', form_data)
        first_alternative = alternatives['translations'][0]
        second_alternative = alternatives['translations'][1]

        assert first_alternative is not None
        assert second_alternative  is not None
        assert first_alternative["likelihood"] > second_alternative["likelihood"]

    def test_get_translation_where_gslobe_fails_but_translate_succeeds(self):

        form_data = dict(
            url='http://mir.lu',
            context='Die krassen Jägermeister',
            word="krassen")
        alternatives = self.json_from_api_post('/get_possible_translations/de/en', form_data)

        first_alternative = alternatives['translations'][0]
        assert first_alternative is not None

    def test_translate_and_bookmark(self):

        form_data = dict(
            url='http://mir.lu',
            context='Die kleine Jägermeister',
            word="Die")

        bookmark1 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        bookmark2 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        bookmark3  = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)

        assert (bookmark1["bookmark_id"] == bookmark2["bookmark_id"] == bookmark3["bookmark_id"])

        form_data["word"] = "kleine"
        bookmark4  = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        self.assertTrue(bookmark4['translation'] in ['small', 'little'])
