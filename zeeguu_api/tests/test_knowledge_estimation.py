# -*- coding: utf8 -*-
import json
from unittest import TestCase
from zeeguu_api.tests.api_test_mixin import APITestMixin

example1_word = 'Freund'
example1_post_url = '/bookmark_with_context/de/{0}/en/friend'.format(example1_word)
example1_context = 'Mein Freund lächelte'
example1_context_url = 'http://www.derkleineprinz-online.de/text/2-kapitel/'
example1_payload = dict(context=example1_context, url=example1_context_url)


class KnowledgeEstimationTest(APITestMixin, TestCase):

    #
    def test_too_easy_makes_bookmark_learned(self):

        self.api_post(example1_post_url, example1_payload)

        bookmarks_by_day = self.json_from_api_get('/bookmarks_by_day/with_context')
        bookmarks_today = bookmarks_by_day[0]['bookmarks']
        last_bookmark_id = bookmarks_today[0]['id']

        assert any(b['context'] == example1_context for b in bookmarks_today)

        exercise_log = self.json_from_api_get('/get_exercise_log_for_bookmark/{0}'.format(last_bookmark_id))
        assert not exercise_log

        known_bookmarks = self.json_from_api_get('/get_known_bookmarks/de')
        assert not known_bookmarks

        self.api_post( '/report_exercise_outcome/Too easy/Recognize/10000/{0}'.format(last_bookmark_id))

        exercise_log = self.json_from_api_get('/get_exercise_log_for_bookmark/{0}'.format(last_bookmark_id))
        assert exercise_log[0]['outcome'] == 'Too easy'

        known_bookmarks = self.json_from_api_get('/get_known_bookmarks/de')
        assert known_bookmarks
        assert known_bookmarks[0]['origin'] == example1_word


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
