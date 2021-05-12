from random import randint

from zeeguu_core_test.rules.base_rule import BaseRule
from zeeguu_core_test.rules.language_rule import LanguageRule
from zeeguu_core_test.rules.url_rule import UrlRule
from zeeguu_core.model import RSSFeed, Language, Url
from zeeguu_core_test.test_data.mocking_the_web import url_spiegel_rss, icon_name_spiegel


class RSSFeedRule(BaseRule):
    """

        Creates a RSSFeed object with random data and saves it to the database

    """

    def __init__(self):
        super().__init__()

        self.rss_feed = self._create_model_object()
        self.feed = self.rss_feed
        self.save(self.rss_feed)

        lang1 = Language.find_or_create('de')
        url = Url.find_or_create(self.db.session, url_spiegel_rss)

        self.feed1 = RSSFeed.find_or_create(self.db.session, url, "", "", icon_name_spiegel,
                                            language=lang1)
        self.save(self.feed1)

    @staticmethod
    def _exists_in_db(obj):
        return RSSFeed.exists(obj)

    def _create_model_object(self):
        title = " ".join(self.faker.text().split()[:(randint(1, 10))])
        description = " ".join(self.faker.text().split()[:(randint(5, 20))])
        language = LanguageRule().random
        url = UrlRule().url
        image_url = UrlRule().url
        icon_name = self.faker.name()

        new_rss_feed = RSSFeed(url, title, description, image_url, icon_name, language)

        if RSSFeed.exists(new_rss_feed):
            return self._create_model_object()

        return new_rss_feed
