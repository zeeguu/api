from unittest import TestCase

import zeeguu.core
from zeeguu.core.model import Feed
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.url_rule import UrlRule

db_session = zeeguu.core.model.db.session


class FeedCountryTest(ModelTestMixIn, TestCase):
    """
    A feed's country is what a learner's variety preference is matched against,
    so it has to survive creation -- and its absence has to stay absent, since
    untagged must never be filtered out.
    """

    def setUp(self):
        super().setUp()
        self.language = LanguageRule().fr

    def _feed(self, title, country=None):
        return Feed.find_or_create(
            db_session,
            UrlRule().url,
            title,
            "a description",
            icon_name="icon.png",
            language=self.language,
            feed_type=0,
            country=country,
        )

    def test_a_feed_remembers_where_it_publishes_from(self):
        assert self._feed("Belgian feed", country="BE").country == "BE"

    def test_a_feed_created_without_a_country_stays_untagged(self):
        # Every feed that predates varieties is in this state, and the filter has
        # to keep serving them to everyone.
        assert self._feed("Untagged feed").country is None
