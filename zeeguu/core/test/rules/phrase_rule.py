from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.model.phrase import Phrase


class PhraseRule(BaseRule):
    """
    Creates a Phrase with random data and saves it to the database.
    """

    def __init__(self, word=None, language=None):
        super().__init__()

        self.phrase = self._create_model_object(word, language)

        if not self._exists_in_db(self.phrase):
            self.save(self.phrase)

    def _create_model_object(self, word=None, language=None):
        tmp_word = word
        tmp_language = language

        if tmp_word is None:
            tmp_word = self.faker.word()

        if tmp_language is None:
            tmp_language = LanguageRule().random

        phrase = Phrase(tmp_word, tmp_language)

        if self._exists_in_db(phrase):
            return self._create_model_object(word, language)

        return phrase

    @staticmethod
    def _exists_in_db(obj):
        return Phrase.exists(obj.content, obj.language)
