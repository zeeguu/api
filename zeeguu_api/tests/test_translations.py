# coding=utf-8
from unittest import TestCase

from api_test_mixin import APITestMixin


class TranslationTests(APITestMixin, TestCase):

    def test_translate(self):
        form_data = dict(
            url='http://mir.lu',
            context=u'Die kleine Jägermeister',
            word="Die")
        rv = self.api_post('/translate/de/en', form_data)
        # print rv.data

    def test_get_possible_translations(self):
        form_data = dict(
            url='http://mir.lu',
            context=u'Die kleine Jägermeister',
            word="kleine")
        alternatives = self.json_from_api_post('/get_possible_translations/de/en', form_data)

        first_alternative = alternatives['translations'][0]
        second_alternative = alternatives['translations'][1]

        assert first_alternative is not None
        assert second_alternative  is not None
        assert first_alternative["likelihood"] > second_alternative["likelihood"]

    def test_get_translation_where_gslobe_fails_but_translate_succeeds(self):

        form_data = dict(
            url='http://mir.lu',
            context=u'Die krassen Jägermeister',
            word="krassen")
        alternatives = self.json_from_api_post('/get_possible_translations/de/en', form_data)

        first_alternative = alternatives['translations'][0]
        assert first_alternative is not None


    # def test_same_text_does_not_get_created_multiple_Times(self):
    #
    #     context = u'Die kleine Jägermeister'
    #     # with zeeguu.app.app_context():
    #     #     url = Url.find('http://mir.lu/stories/german/jagermeister', "Die Kleine Jagermeister (Mircea's Stories)")
    #     #     source_language = Language.find('de')
    #     #
    #     form_data = dict(
    #         url=url.as_string(),
    #         context=context,
    #         word="Die")
    #
    #     self.api_post('/translate_and_bookmark/de/en', form_data)
    #     text1 = Text.find_or_create(context, source_language, url)
    #     self.api_post('/translate_and_bookmark/de/en', form_data)
    #     text2 = Text.find_or_create(context, source_language, url)
    #     assert (text1 == text2)


    def test_translate_and_bookmark(self):

        form_data = dict(
            url='http://mir.lu',
            context=u'Die kleine Jägermeister',
            word="Die")

        bookmark1 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        bookmark2 = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        bookmark3  = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        # print bookmark3

        assert (bookmark1["bookmark_id"] == bookmark2["bookmark_id"] == bookmark3["bookmark_id"])

        form_data["word"] = "kleine"
        bookmark4  = self.json_from_api_post('/translate_and_bookmark/de/en', form_data)
        # print bookmark4
