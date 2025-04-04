from datetime import datetime, timedelta
from random import randint

from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.model.source import Source


class SourceRule(BaseRule):
    """

    Creates an Source object with random data and saves it to the database.

    """

    def __init__(self):
        super().__init__()

        self.source = self._create_model_object()
        self.save(self.source)

    def _create_model_object(self):
        from zeeguu.core.test.rules.language_rule import LanguageRule
        from zeeguu.core.test.rules.source_text_rule import SourceTextRule
        from zeeguu.core.model.source_type import SourceType

        source_text_rule = SourceTextRule()
        source_type = SourceType.find_by_type(SourceType.ARTICLE)
        language = LanguageRule().random
        broken = 0
        source = Source(source_text_rule.source_text, source_type, language, broken)

        return source
