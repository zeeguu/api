from random import randint

from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.url_rule import UrlRule
from zeeguu.core.model import Feed, Language, Url
from zeeguu.core.feed_handler import FEED_TYPE, NewspaperFeed
from zeeguu.core.test.mocking_the_web import (
    URL_SPIEGEL_RSS,
    URL_LEMONDE_VOLS_AMERICAINS,
    URL_VERDENS_BEDSTE
)


class FeedRule(BaseRule):
    """

    Creates a Feed object with random data and saves it to the database

    """

    def __init__(self):
        super().__init__()

        self.fake_feed = self._create_model_object()
        self.feed = self.fake_feed
        self.save(self.feed)

        lang_de = Language.find_or_create("de")
        url = Url.find_or_create(self.db.session, URL_SPIEGEL_RSS)
        # We need to address the new FeedType
        self.feed1 = Feed.find_or_create(
            self.db.session,
            url,
            "",
            "",
            "spiegel.png",
            language=lang_de,
            feed_type=FEED_TYPE["rss"],
        )
        self.save(self.feed1)

        lang_fr = Language.find_or_create("fr")
        url = Url.find_or_create(self.db.session, URL_LEMONDE_VOLS_AMERICAINS)

        self.feed_fr = Feed.find_or_create(
            self.db.session,
            url,
            "",
            "",
            "spiegel.png",
            language=lang_fr,
            feed_type=FEED_TYPE["rss"],
        )
        self.save(self.feed_fr)

        lang_da = Language.find_or_create("da")
        url = Url.find_or_create(self.db.session, URL_VERDENS_BEDSTE)
        self.feed_newspaper_da = Feed.find_or_create(
            self.db.session,
            url,
            "",
            "",
            "verdensbedstenyheder.png",
            lang_da,
            FEED_TYPE["newspaper"]
        )
        # For testing, we create an object that doens't cache the articles.
        self.feed_newspaper_da.feed_handler = NewspaperFeed(str(self.feed_newspaper_da.url), FEED_TYPE["newspaper"], False)
        self.save(self.feed_newspaper_da)
        

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
