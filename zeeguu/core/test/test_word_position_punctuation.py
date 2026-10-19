from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.tokenization.word_position_finder import find_first_occurrence


class WordPositionPunctuationTest(ModelTestMixIn):
    """Punctuation normalizes to "", which is a substring of every word."""

    def test_a_missing_word_is_not_found_on_a_blank_or_full_stop(self):
        da = LanguageRule.get_or_create_language("da")
        result = find_first_occurrence("selv", "_____ min bedstemor bruger internettet.", da)
        assert not result["found"], result

    def test_words_with_punctuation_inside_are_still_found(self):
        fr = LanguageRule.get_or_create_language("fr")
        de = LanguageRule.get_or_create_language("de")
        assert find_first_occurrence("qu’ à", "Tu n’as qu’ à demander.", fr)["found"]
        assert find_first_occurrence("z. B.", "Viele Früchte, z. B. Äpfel, sind gesund.", de)["found"]
