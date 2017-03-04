# coding=utf-8

from unittest import TestCase

from api_test_mixin import APITestMixin


class UserStatsTests(APITestMixin, TestCase):

    def setUp(self):
        self.maximal_populate = True
        super(UserStatsTests, self).setUp()

    def test_get_lower_bound_percentage_of_vocabulary(self):
        rv_basic = self.api_get('/get_lower_bound_percentage_of_basic_vocabulary')
        rv_extended = self.api_get('/get_lower_bound_percentage_of_extended_vocabulary')
        basic_lower_bound = float (rv_basic.data)
        extended_lower_bound = float (rv_extended.data)
        assert basic_lower_bound > extended_lower_bound > 0

    #
    def test_get_upper_bound_percentage_of_vocabulary(self):
        rv_basic = self.api_get('/get_upper_bound_percentage_of_basic_vocabulary')
        rv_extended = self.api_get('/get_upper_bound_percentage_of_extended_vocabulary')
        basic_upper_bound = float (rv_basic.data)
        extended_upper_bound = float (rv_extended.data)
        assert 1 > basic_upper_bound > extended_upper_bound

    #
    def test_get_percentage_of_probably_known_bookmarked_words(self):
        rv = self.api_get('/get_percentage_of_probably_known_bookmarked_words')
        assert 0 <= float(rv.data) < 1
