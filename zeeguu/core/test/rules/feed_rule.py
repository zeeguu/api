from random import randint

from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.url_rule import UrlRule
from zeeguu.core.model import Feed


class FeedRule(BaseRule):
    """

    Creates a Feed object with random data and saves it to the database

    """

    def __init__(self):
        super().__init__()

        self.fake_feed = self._create_model_object()
        self.feed = self.fake_feed
        self.save(self.feed)

    @staticmethod
    def _exists_in_db(obj):
        return Feed.exists(obj)

    def _create_model_object(self):
        title = " ".join(self.faker.text().split()[: (randint(1, 10))])
        description = " ".join(self.faker.text().split()[: (randint(5, 20))])
        language = LanguageRule().random
        url = UrlRule().url
        image_url = UrlRule().url
        icon_name = self.faker.name()

        new_feed = Feed(url, title, description, image_url, icon_name, language)

        if Feed.exists(new_feed):
            return self._create_model_object()

        return new_feed
