from unittest.mock import patch

import requests

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.tokenization.stanza_client import StanzaServiceClient
from zeeguu.core.tokenization.word_position_finder import validate_single_occurrence


class WordPositionNltkFallbackTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.de = LanguageRule.get_or_create_language("de")

    def test_saving_a_bookmark_survives_a_stanza_outage(self):
        down = requests.ConnectionError("stanza service unreachable")
        with patch.object(StanzaServiceClient, "tokenize_text", side_effect=down):
            result = validate_single_occurrence("große", "Der große Hund bellt", self.de)

        assert result["valid"], result
        assert result["position_data"]["token_i"] == 1
        assert result["position_data"]["total_tokens"] == 1

    def test_other_errors_are_not_masked_by_the_fallback(self):
        # only an unreachable/failing service falls back; a bug still fails
        with patch.object(StanzaServiceClient, "tokenize_text", side_effect=KeyError("bug")):
            result = validate_single_occurrence("große", "Der große Hund bellt", self.de)

        assert result["error_type"] == "tokenization_failed"
