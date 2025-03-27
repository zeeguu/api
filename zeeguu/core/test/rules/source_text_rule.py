from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.model.source_text import SourceText


class SourceTextRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.source_text model class.

    Creates a SourceText object with random data and saves it to the database.
    """

    def __init__(self, text=None, length=59):
        super().__init__()

        self.source_text = self._create_model_object(text, length=length)

        self.save(self.source_text)

    def _create_model_object(self, content=None, length=100):
        if content is None:
            content = self.faker.text(max_nb_chars=length)

        source_text = SourceText(content)

        return source_text
