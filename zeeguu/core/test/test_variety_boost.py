import json
from unittest import TestCase

import zeeguu.core
from zeeguu.core.elastic.elastic_query_builder import build_elastic_recommender_query
from zeeguu.core.model import UserLanguage
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.user_rule import UserRule

db_session = zeeguu.core.model.db.session


def a_query(variety=None):
    return build_elastic_recommender_query(
        10, "", "", None, "1d", "1d", 0.6, "", "", [], variety=variety
    )


class VarietyBoostTest(TestCase):
    """
    The preference lifts a country; it never removes the rest. With three Belgian
    feeds against dozens of Dutch ones, a filter would hand a Flemish reader an
    empty page.
    """

    def test_a_variety_adds_a_weighted_function(self):
        functions = a_query("BE")["query"]["function_score"]["functions"]

        assert {"filter": {"match": {"country": "BE"}}, "weight": 3.0} in functions

    def test_recency_still_applies_alongside_it(self):
        functions = a_query("BE")["query"]["function_score"]["functions"]

        assert any("exp" in each for each in functions)

    def test_no_variety_leaves_the_query_as_it_was(self):
        assert a_query(None) == a_query()
        assert len(a_query()["query"]["function_score"]["functions"]) == 1

    def test_the_country_never_becomes_a_filter(self):
        # The whole design rests on this: an article from an untagged feed, or
        # from no feed at all, has to stay eligible for everyone.
        query = a_query("BE")
        bool_part = json.dumps(query["query"]["function_score"]["query"]["bool"])

        assert "country" not in bool_part


class VarietyForTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.language = LanguageRule().fr

    def test_no_row_means_no_preference(self):
        assert UserLanguage.variety_for(self.user, self.language) is None

    def test_a_row_without_a_variety_means_no_preference(self):
        UserLanguage.find_or_create(db_session, self.user, self.language)

        assert UserLanguage.variety_for(self.user, self.language) is None

    def test_the_stored_variety_is_what_comes_back(self):
        row = UserLanguage.find_or_create(db_session, self.user, self.language)
        row.variety = "BE"
        db_session.add(row)
        db_session.commit()

        assert UserLanguage.variety_for(self.user, self.language) == "BE"

    def test_a_variety_belongs_to_one_language_only(self):
        row = UserLanguage.find_or_create(db_session, self.user, self.language)
        row.variety = "BE"
        db_session.add(row)
        db_session.commit()

        other = LanguageRule().de
        assert UserLanguage.variety_for(self.user, other) is None
