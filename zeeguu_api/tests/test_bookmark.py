# coding=utf-8

import json
from unittest import TestCase
from api_test_mixin import APITestMixin

import zeeguu

example1_post_url = '/bookmark_with_context/de/Freund/en/friend'
example1_context = u'Mein Freund lächelte'
example1_context_url = 'http://www.derkleineprinz-online.de/text/2-kapitel/'
example1_payload = dict(context=example1_context, url=example1_context_url)


class BookmarkTest(APITestMixin, TestCase):

    def test_last_bookmark_added_is_first_in_bookmarks_by_day(self):

        new_bookmark_id = self.raw_data_from_api_post(example1_post_url,
            example1_payload)

        bookmarks_on_first_day = self.json_from_api_get('/bookmarks_by_day/with_context')[0]["bookmarks"]

        assert int(new_bookmark_id) == bookmarks_on_first_day[0]["id"]

    def test_context_parameter_functions_in_bookmarks_by_day(self):
        elements  = self.json_from_api_get ('/bookmarks_by_day/with_context')
        some_date = elements[0]
        assert some_date ["date"]

        some_bookmark = some_date ["bookmarks"][0]
        for key in ["from", "to", "id", "context", "title", "url"]:
            assert key in some_bookmark

        # if we don't pass the context argument, we don't get
        # the context
        elements = self.json_from_api_get ('/bookmarks_by_day/no_context')
        some_date = elements[0]
        some_contrib = some_date ["bookmarks"][0]
        assert not "context" in some_contrib

    #
    def test_delete_bookmark3(self):
        self.api_post("delete_bookmark/1")
        bookmarks = self.json_from_api_get('/bookmarks_by_day/with_context')
        assert len(bookmarks) == zeeguu.populate.TEST_BOOKMARKS_COUNT - 1

    def test_delete_translation_from_bookmark(self):
        translations_dict_of_bookmark = self.json_from_api_get('/get_translations_for_bookmark/1')
        first_word_translation_of_bookmark = translations_dict_of_bookmark[0]['word']

        assert 'FAIL' == self.raw_data_from_api_post('/delete_translation_from_bookmark/1/' + str(first_word_translation_of_bookmark))
        self.api_post('/add_new_translation_to_bookmark/love/1')

        translations_dict_of_bookmark  = self.json_from_api_get('/get_translations_for_bookmark/1')
        first_word_translation_of_bookmark = translations_dict_of_bookmark[0]['word']

        assert len(translations_dict_of_bookmark) == 2
        assert any (translation['word'] == first_word_translation_of_bookmark for translation in translations_dict_of_bookmark)
        assert any(translation['word'] == 'love' for translation in translations_dict_of_bookmark)

        assert 'FAIL' == self.raw_data_from_api_post('/delete_translation_from_bookmark/1/lov')
        assert 'OK' == self.raw_data_from_api_post('/delete_translation_from_bookmark/1/' + str(first_word_translation_of_bookmark))

        translations_dict_of_bookmark = self.json_from_api_get('/get_translations_for_bookmark/1')
        assert not any(translation['word'] == first_word_translation_of_bookmark for translation in translations_dict_of_bookmark)

    def test_get_translations_for_bookmark(self):
        translations_dict_bookmark_before_add = self.json_from_api_get('/get_translations_for_bookmark/1')
        assert len(translations_dict_bookmark_before_add) ==1

        first_translation_word = translations_dict_bookmark_before_add[0]['word']
        assert any(translation['word'] == first_translation_word for translation in translations_dict_bookmark_before_add)
        rv = self.api_post('/add_new_translation_to_bookmark/love/1')
        assert rv.data == "OK"
        rv = self.api_get('/get_translations_for_bookmark/1')
        translations_dict_bookmark_after_add = json.loads(rv.data)
        assert len(translations_dict_bookmark_after_add) ==2
        assert first_translation_word!= 'love'
        assert any(translation['word'] == first_translation_word for translation in translations_dict_bookmark_after_add)
        assert any(translation['word'] == 'love' for translation in translations_dict_bookmark_after_add)


