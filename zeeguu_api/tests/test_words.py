import json
import re
from unittest import TestCase

from api_test_mixin import APITestMixin


class WordsTests(APITestMixin, TestCase):

    def test_get_not_looked_up_words(self):
        rv = self.api_get('/bookmarks_by_day/with_context')
        bookmarks_by_day = []
        bookmarks_by_day_with_date = json.loads(rv.data)

        rv = self.api_get('/get_not_looked_up_words/de')
        estimated_user_voc_before = json.loads(rv.data)
        # print estimated_user_voc_before

        assert not any(word == 'es' for word in estimated_user_voc_before)
        assert not any(word == 'an' for word in estimated_user_voc_before)
        assert not any(word == 'auch' for word in estimated_user_voc_before)
        for i in range(0, len(bookmarks_by_day_with_date)):
            for j in range(0, len(bookmarks_by_day_with_date[i]['bookmarks'])):
                bookmarks_by_day.append(bookmarks_by_day_with_date[i]['bookmarks'][j]['context'])
        for bookmark in bookmarks_by_day:
            bookmark_content_words = re.sub("[^\w]", " ", bookmark).split()
            assert not 'es' in bookmark_content_words
            assert not 'an' in bookmark_content_words
            assert not 'auch' in bookmark_content_words

        # We need to send three post requests such
        # that the knowledge estimator sees the user
        # encounter these words three times and increases
        # their probability of being "not looked up"

        form_data = dict(
            url='http://mir.lu',
            context='es an auch')
        rv = self.api_post('/bookmark_with_context/de/auch/en/also', form_data)
        form_data = dict(
            url='http://mir.lu/2',
            context='es an auch der')
        rv = self.api_post('/bookmark_with_context/de/der/en/the', form_data)
        form_data = dict(
            url='http://mir.lu/3',
            context='es an auch den')
        rv = self.api_post('/bookmark_with_context/de/den/en/the', form_data)

        rv = self.api_get('/get_not_looked_up_words/de')
        estimated_user_voc_after = json.loads(rv.data)
        # print estimated_user_voc_after

        assert len(estimated_user_voc_after) == len(estimated_user_voc_before) + 2
        assert any(word == 'es' for word in estimated_user_voc_after)
        assert any(word == 'an' for word in estimated_user_voc_after)
        assert not any(word == 'auch' for word in estimated_user_voc_after)
