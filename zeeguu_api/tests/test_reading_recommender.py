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

