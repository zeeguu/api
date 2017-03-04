# -*- coding: utf8 -*-
import json
from unittest import TestCase
from api_test_mixin import APITestMixin
import zeeguu

example1_word = 'Freund'
example1_post_url = '/bookmark_with_context/de/{0}/en/friend'.format(example1_word)
example1_context = u'Mein Freund lächelte'
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

    #
    #
    def test_get_known_words(self):

        known_words_before = self.json_from_api_get('/get_known_words/de')
        assert not known_words_before

        bookmark_id = self.api_post(example1_post_url, example1_payload).data
        self.api_post( '/report_exercise_outcome/Too easy/Recognize/10000/{0}'.format(bookmark_id))

        known_words_after = self.json_from_api_get('/get_known_words/de')
        print known_words_after
        assert example1_word in known_words_after

    #
    # note that this is about PROBABLY KNOWN WORDS.... KNOWN WORDS are tested elsewhere!
    def test_multiple_correct_makes_word_probably_known(self):

        probably_known_words = self.json_from_api_get('/get_probably_known_words/de')

        # Initially none of the words is known
        assert not any(word['word'] == example1_word for word in probably_known_words)

        # Bookmark 'sondern'
        new_bookmark_id = (self.api_post(example1_post_url, example1_payload)).data

        # User does three correct exercises
        user_recognizes_word = '/report_exercise_outcome/Correct/Recognize/10000/{0}'.format(new_bookmark_id)
        assert self.api_post(user_recognizes_word).data == "OK"
        assert self.api_post(user_recognizes_word).data == "OK"
        assert self.api_post(user_recognizes_word).data == "OK"

        # Thus, Freund goes to the Probably known words
        probably_known_words = self.json_from_api_get('/get_probably_known_words/de')
        assert any(word == example1_word for word in probably_known_words)


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

    def test_feedback_from_smartwartch_updates_bookmarks_to_study(self):
        to_study = self.json_from_api_get("bookmarks_to_study/50")
        to_study_count_before = len(to_study)
        assert len(to_study) == zeeguu.populate.TEST_BOOKMARKS_COUNT

        # Create an learnedIt event
        learned_bookmark_id = to_study[0]["id"]
        events = [
            dict(
                bookmark_id=to_study[0]["id"],
                time="2016-05-05T10:10:10",
                event="learnedIt"
            ),
            dict(
                bookmark_id=to_study[1]["id"],
                time="2016-05-05T10:11:10",
                event="wrongTranslation"
                # NOTE: Wrong Translation is something that the user provides
                # as feedback in the smartwatch application to say: Don't show
                # me this word again, i think it's a wrong translation... this is
                # why neither bookmark 1 nor bookmark 2 are being shown at the end
                #
            )
        ]
        result = self.api_post('/upload_smartwatch_events', dict(events=json.dumps(events)))
        assert (result.data == "OK")

        to_study = self.json_from_api_get("bookmarks_to_study/50")
        assert not to_study
