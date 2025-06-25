from zeeguu.core.model import Meaning, UserWord
from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.model.phrase import Phrase
from zeeguu.core.test.rules.phrase_rule import PhraseRule


class UserWordRule(BaseRule):
    """
    Creates a Phrase with random data and saves it to the database.
    """

    def __init__(self, user, meaning):
        super().__init__()

        self.user_word = self._create_model_object(user, meaning)

        if not self._exists_in_db(self.user_word):
            self.save(self.user_word)

    def _create_model_object(self, user=None, meaning=None):
        tmp_user = user
        tmp_meaning = meaning

        if tmp_user is None:
            tmp_user = PhraseRule().phrase

        if tmp_meaning is None:
            tmp_meaning = PhraseRule().phrase

        user_word = UserWord(tmp_user, tmp_meaning)

        if self._exists_in_db(user_word):
            return self._create_model_object(tmp_user, tmp_meaning)

        return user_word

    @staticmethod
    def _exists_in_db(obj):
        return UserWord.exists(obj.user, obj.meaning)
