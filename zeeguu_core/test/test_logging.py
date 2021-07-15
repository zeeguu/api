from unittest import TestCase

import zeeguu_core


class LanguageTest(TestCase):

    def test_languages_exists(self):
        zeeguu_core.log("tüst")
