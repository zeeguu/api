from zeeguu.core.model import Meaning
from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.model.phrase import Phrase
from zeeguu.core.test.rules.phrase_rule import PhraseRule


class MeaningRule(BaseRule):
    """
    Creates a Phrase with random data and saves it to the database.
    """

    def __init__(self, origin=None, translation=None):
        super().__init__()

        self.meaning = self._create_model_object(origin, translation)

        if not self._exists_in_db(self.meaning):
            self.save(self.meaning)

    def _create_model_object(self, origin=None, translation=None):
        tmp_origin = origin
        tmp_translation = translation

        if tmp_origin is None:
            tmp_origin = PhraseRule().phrase

        if tmp_translation is None:
            tmp_translation = PhraseRule().phrase

        meaning = Meaning(tmp_origin, tmp_translation)

        if self._exists_in_db(meaning):
            return self._create_model_object(tmp_origin, tmp_translation)

        return meaning

    @staticmethod
    def _exists_in_db(obj):
        return Meaning.exists(obj.origin, obj.translation)
