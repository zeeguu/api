from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.language.strategies.default_difficulty_estimator import DefaultDifficultyEstimator

SIMPLE_TEXT = "Das ist "
COMPLEX_TEXT = "Alle hatten in sein Lachen eingestimmt, hauptsächlich aus Ehrerbietung " \
               "gegen das Familienoberhaupt"

class DefaultDifficultyEstimatorTest(ModelTestMixIn, TestCase):

    def setUp(self):
        super().setUp()
        self.lan = LanguageRule().de
        self.user = UserRule().user

    def test_compute_simple_text_difficulty(self):
        d1 = DefaultDifficultyEstimator.estimate_difficulty(SIMPLE_TEXT, self.lan, self.user)

        assert d1['discrete'] == 'EASY'
        assert d1['normalized'] == 0

    def test_compute_complex_text_difficulty(self):
        d1 = DefaultDifficultyEstimator.estimate_difficulty(COMPLEX_TEXT, self.lan, self.user)

        assert d1['discrete'] == 'EASY'
        assert d1['normalized'] == 0