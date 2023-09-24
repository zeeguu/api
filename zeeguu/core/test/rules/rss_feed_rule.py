from random import randint

from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.url_rule import UrlRule
from zeeguu.core.model import RSSFeed, Language, Url
from zeeguu.core.test.mocking_the_web import (
    URL_SPIEGEL_RSS,
    URL_LEMONDE_VOLS_AMERICAINS
)


class RSSFeedRule(BaseRule):
    """

    Creates a RSSFeed object with random data and saves it to the database

    """

    def __init__(self):
        super().__init__()

        self.rss_feed = self._create_model_object()
        self.feed = self.rss_feed
        self.save(self.rss_feed)

        lang_de = Language.find_or_create("de")
        url = Url.find_or_create(self.db.session, URL_SPIEGEL_RSS)

        self.feed1 = RSSFeed.find_or_create(
            self.db.session, url, "", "", "spiegel.png", language=lang_de
        )
        self.save(self.feed1)

        lang_fr = Language.find_or_create("fr")
        url = Url.find_or_create(self.db.session, URL_LEMONDE_VOLS_AMERICAINS)

        self.feed_fr = RSSFeed.find_or_create(
            self.db.session, url, "", "", "spiegel.png", language=lang_fr
        )
        self.save(self.feed_fr)

    @staticmethod
    def _exists_in_db(obj):
        return RSSFeed.exists(obj)

    def _create_model_object(self):
        title = " ".join(self.faker.text().split()[: (randint(1, 10))])
        description = " ".join(self.faker.text().split()[: (randint(5, 20))])
        language = LanguageRule().random
        url = UrlRule().url
        image_url = UrlRule().url
        icon_name = self.faker.name()

        new_rss_feed = RSSFeed(url, title, description, image_url, icon_name, language)

        if RSSFeed.exists(new_rss_feed):
            return self._create_model_object()

        return new_rss_feed
