from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.model.user_word import UserWord


class UserWordRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.UserWord model class.

    Creates a UserWord object with random data and saves it to the database.
    """

    def __init__(self, word=None, language=None):
        super().__init__()

        self.user_word = self._create_model_object(word, language)

        if not self._exists_in_db(self.user_word):
            self.save(self.user_word)

    def _create_model_object(self, word=None, language=None):
        tmp_word = word
        tmp_language = language

        if tmp_word is None:
            tmp_word = self.faker.word()

        if tmp_language is None:
            tmp_language = LanguageRule().random

        user_word = UserWord(tmp_word, tmp_language)

        if self._exists_in_db(user_word):
            return self._create_model_object(word, language)

        return user_word

    @staticmethod
    def _exists_in_db(obj):
        return UserWord.exists(obj.word, obj.language)
