from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.model.new_text import NewText


class NewTextRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.NewText model class.

    Creates a Text object with random data and saves it to the database.
    """

    def __init__(self, text=None, length=59):
        super().__init__()

        self.text = self._create_model_object(text, length=length)

        self.save(self.text)

    def _create_model_object(self, content=None, length=100):
        if content is None:
            content = self.faker.text(max_nb_chars=length)

        text = NewText(content)

        return text
