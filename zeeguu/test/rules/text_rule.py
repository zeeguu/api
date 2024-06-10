from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.url_rule import UrlRule
from zeeguu.core.model.text import Text


class TextRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.Text model class.

    Creates a Text object with random data and saves it to the database.
    """

    def __init__(self, length=59):
        super().__init__()

        self.text = self._create_model_object(length)

        self.save(self.text)

    def _create_model_object(self, length):
        random_content = self.faker.text(max_nb_chars=length)
        random_language = LanguageRule().random

        random_article = ArticleRule().article
        random_url = random_article.url

        text = Text(random_content, random_language, random_url, random_article )

        if self._exists_in_db(text):
            return self._create_model_object(length)

        return text

    @staticmethod
    def _exists_in_db(obj):
        """An database existence check is not necessary since no primary key
        constraints can be violated.

        """
        return False
