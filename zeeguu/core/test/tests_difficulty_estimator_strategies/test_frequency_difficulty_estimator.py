from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.language.difficulty_estimator_factory import DifficultyEstimatorFactory

SIMPLE_TEXT = "Das ist "
COMPLEX_TEXT = "Alle hatten in sein Lachen eingestimmt, hauptsächlich aus Ehrerbietung " \
               "gegen das Familienoberhaupt"


class FrequencyDifficultyEstimatorTest(ModelTestMixIn, TestCase):

    def setUp(self):
        super().setUp()
        self.lan = LanguageRule().de
        self.user = UserRule().user

    def test_compute_very_simple_text_difficulty(self):
        estimator = DifficultyEstimatorFactory.get_difficulty_estimator("frequency")
        d1 = estimator.estimate_difficulty(SIMPLE_TEXT, self.lan, self.user)

        assert d1['discrete'] == 'EASY'
        assert d1['normalized'] < 0.1
