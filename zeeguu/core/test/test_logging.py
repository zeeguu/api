from unittest import TestCase

import zeeguu.core


class LanguageTest(TestCase):

    def test_languages_exists(self):
        zeeguu.core.log("tüst")
