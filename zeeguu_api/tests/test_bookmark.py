# coding=utf-8

import json
from unittest import TestCase

from zeeguu_api.tests.api_test_mixin import APITestMixin

import zeeguu

example1_post_url = '/contribute_translation/de/en'
example1_context = 'Mein Freund lächelte'
example1_context_url = 'http://www.derkleineprinz-online.de/text/2-kapitel/'
example1_payload = dict(word='Freund', translation='friend', context=example1_context, url=example1_context_url)


class BookmarkTest(APITestMixin, TestCase):

    def test_last_bookmark_added_is_first_in_bookmarks_by_day(self):

        new_bookmark_id = self.json_from_api_post(example1_post_url, example1_payload)["bookmark_id"]

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


    def test_upload_translation(self):

        # GIVEN
        elements  = self.json_from_api_get ('/bookmarks_by_day/with_context')
        day1 = elements[0]
        bookmark1 = day1 ["bookmarks"][0]

        # WHEN
        data = dict(word=bookmark1['from'],
                    url=bookmark1['url'],
                    title=bookmark1 ['title'],
                    context=bookmark1['context'],
                    translation="lamb")

        self.api_post('contribute_translation/de/en',data)

        # THEN

        elements = self.json_from_api_get('/bookmarks_by_day/with_context')
        day1 = elements[0]
        bookmark1 = day1["bookmarks"][0]
        self.assertTrue("lamb" in str(bookmark1))

    def test_get_known_bookmarks_after_date(self):
        """
        The dates in which we have bookmarks in the test data are: 2014, 2011, 2001
        :return:
        """
        def first_day_of(year):
            return str(year)+"-01-01T00:00:00"

        form_data = dict()
        bookmarks = self.json_from_api_post('/bookmarks_by_day', form_data)
        # If we don't ask for the context, we don't get it
        assert "context" not in bookmarks[0]["bookmarks"][0]
        # Also, since we didn't pass any after_date we get all the three days
        assert len(bookmarks) == 1

        # No bookmarks in the tests after 2015
        form_data["after_date"]=first_day_of(2015)
        bookmarks = self.json_from_api_post('/bookmarks_by_day', form_data)
        assert len(bookmarks) == 0