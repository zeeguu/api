from zeeguu.core.model import Meaning, UserMeaning
from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.model.phrase import Phrase
from zeeguu.core.test.rules.phrase_rule import PhraseRule


class UserMeaningRule(BaseRule):
    """
    Creates a Phrase with random data and saves it to the database.
    """

    def __init__(self, user, meaning):
        super().__init__()

        self.user_meaning = self._create_model_object(user, meaning)

        if not self._exists_in_db(self.user_meaning):
            self.save(self.user_meaning)

    def _create_model_object(self, user=None, meaning=None):
        tmp_user = user
        tmp_meaning = meaning

        if tmp_user is None:
            tmp_user = PhraseRule().phrase

        if tmp_meaning is None:
            tmp_meaning = PhraseRule().phrase

        user_meaning = UserMeaning(tmp_user, tmp_meaning)

        if self._exists_in_db(user_meaning):
            return self._create_model_object(tmp_user, tmp_meaning)

        return user_meaning

    @staticmethod
    def _exists_in_db(obj):
        return UserMeaning.exists(obj.user, obj.meaning)
