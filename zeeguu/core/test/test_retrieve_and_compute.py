import newspaper

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.content_cleaning.content_cleaner import cleanup_non_content_bits
from zeeguu.core.content_quality.quality_filter import (
    sufficient_quality,
    LowQualityTypes,
)

from zeeguu.core.test.mocking_the_web import *


class TestRetrieveAndCompute(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.user = UserRule().user

    def test_sufficient_quality(self):
        art = newspaper.Article(URL_PROPUBLICA_INVESTING)
        art.download()
        art.parse()

        assert sufficient_quality(art)[0]

    def test_new_scientist_overlay(self):
        art = newspaper.Article(URL_NEWSCIENTIST_FISH)
        art.download()
        art.parse()

        is_quality, _, _ = sufficient_quality(art)
        assert not is_quality

    def test_le_monde_subscription(self):
        art = newspaper.Article(URL_LEMONDE_VOLS_AMERICAINS)
        art.download()
        art.parse()

        is_quality, _, _ = sufficient_quality(art)
        assert not is_quality

    def test_fragment_removal(self):
        art = newspaper.Article(URL_ONION_US_MILITARY)
        art.download()
        art.parse()

        cleaned_up_text = cleanup_non_content_bits(art.text)
        assert "Advertisement" not in cleaned_up_text

    def test_ml_classification(self):
        db_content = mock_readability_call(URL_ML_JP_PAYWALL)

        is_quality, reason, code = sufficient_quality(db_content)
        assert not is_quality
        assert reason == "ML Prediction was 'Paywalled'."
        assert code == LowQualityTypes.ML_PREDICTION
