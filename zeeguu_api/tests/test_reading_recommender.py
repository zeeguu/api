import json
from unittest import TestCase
from zeeguu_api.tests.api_test_mixin import APITestMixin



class ReadingRecommenderTests(APITestMixin, TestCase):

    def setUp(self):
        self.maximal_populate = True
        super(ReadingRecommenderTests, self).setUp()

    def test_text_difficulty(self):
        data = """
            {
            "texts":
                [
                    {"content": "Fischers Fritze fischt frische Fische; Frische Fische fischt Fischers Fritze", "id": 1},
                    {"content": "Das ist ein Test.", "id": 2}],
            "difficulty_computer": "default"
            }
        """

        rv = self.api_post('/get_difficulty_for_text/de', data, 'application/json')
        # print rv.data

        difficulties = json.loads(rv.data)['difficulties']
        first_text_difficulty = difficulties[0]
        second_text_difficulty = difficulties[1]

        assert round(first_text_difficulty ['score_average'], 2) > 0.1
        assert first_text_difficulty['estimated_difficulty'] == "HARD"

        assert second_text_difficulty['estimated_difficulty']=="EASY"

    def test_text_learnability(self):
        data = """
            {"texts":
                [
                    {"content": "Der die das besteht warum, wer nicht fragt bleibt jeweils sogar dumm!", "id": 3},
                    {"content": "Dies ist ein weiterer Test!", "id": 4}
                ]
            }
        """

        rv = self.api_post('/get_learnability_for_text/de', data, 'application/json')

        learnabilities = json.loads(rv.data)['learnabilities']
        for learnability in learnabilities:
            assert 0.0 <= learnability['score'] <= 1.0
            if learnability['id'] is 3:
                assert learnability['score']
                assert 0.16 < learnability['score'] < 0.17
            elif learnability['id'] is 4:
                assert learnability['score'] == 0.0
