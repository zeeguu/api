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


def bool_of(query):
    return query["query"]["function_score"]["query"]["bool"]


class VarietyFilterTest(TestCase):
    """
    A variety preference means it. Ranking the country higher instead would leave
    the feed looking untouched, and a setting that visibly does nothing reads as
    a broken app.
    """

    def test_a_variety_is_required_not_merely_preferred(self):
        assert "country" in json.dumps(bool_of(a_query("BE"))["must"])

    def test_no_variety_leaves_the_query_as_it_was(self):
        assert a_query(None) == a_query()
        assert "country" not in json.dumps(bool_of(a_query()))

    def test_the_country_does_not_leak_into_scoring(self):
        # It decides eligibility; recency alone decides order among the eligible.
        functions = a_query("BE")["query"]["function_score"]["functions"]

        assert len(functions) == 1
        assert "exp" in functions[0]

    def test_videos_survive_a_variety_preference(self):
        # This query serves videos too, and a video has no country to match --
        # a channel has no feed. Filtering them on it would delete every video
        # from the feed of anyone who picked a variety.
        clause = [c for c in bool_of(a_query("BE"))["must"] if "bool" in c and "should" in c["bool"]]
        country_clause = [c for c in clause if json.dumps(c).count("country") == 1]

        assert len(country_clause) == 1
        assert {"exists": {"field": "video_id"}} in country_clause[0]["bool"]["should"]

    def test_asking_for_one_country_does_not_exclude_by_another(self):
        # Nothing must land in must_not: the only rule is "from there", and the
        # client explains the empty case rather than the query softening it.
        assert "country" not in json.dumps(bool_of(a_query("BE"))["must_not"])


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
