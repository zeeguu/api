from unittest import TestCase

from zeeguu_api.tests.api_test_mixin import APITestMixin


class Test(APITestMixin, TestCase):

    def test_get_possible_translations(self):
        translations = self.api_post('/get_possible_translations/de/en',
                                               dict(context="das ist sehr schon", url="lalal.is", word="schon", title="lala"))

        print translations.data

