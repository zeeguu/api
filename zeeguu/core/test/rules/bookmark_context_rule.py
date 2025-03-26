import random
import re
from datetime import timedelta

from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.model.bookmark_context import BookmarkContext


class BookmarkContextRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.bookmark_context model class.

    Creates a BookmarkContext object with random data and saves it to the database.
    """

    def __init__(self, text, **kwargs):
        super().__init__()
        self.context = self._create_model_object(text, **kwargs)

        self.save(self.context)

    def _create_model_object(self, text=None, **kwargs):
        bookmark_context = None

        while not bookmark_context:
            from zeeguu.core.test.rules.new_text_rule import NewTextRule
            from zeeguu.core.model.context_type import ContextType
            from zeeguu.core.test.rules.language_rule import LanguageRule

            context_type = ContextType.find_by_type(ContextType.USER_EDITED_TEXT)
            language = LanguageRule().random

            text = NewTextRule(text).text

            bookmark_context = BookmarkContext(
                text,
                context_type,
                language,
                0,
                0,
            )

        return bookmark_context
