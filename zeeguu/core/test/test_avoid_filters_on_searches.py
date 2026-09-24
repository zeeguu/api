"""
The two "avoid" filters -- the Topics to Avoid keyword list and the Avoid
disturbing news toggle -- must survive every path an article can take into a
learner's feed, not just the organic recommender query.

The bug these pin down (#708): a saved-search subscription injected articles
straight past both filters, so a learner who had `trump` on their avoid list and
the disturbing toggle on got a missile-strike article as their top card because
it also matched their `iran` subscription.

The rule the tests encode:

  * disturbing is absolute -- it is a safety setting a teacher or a parent may
    have set, so nothing a learner does switches it off, not even typing a word
    into the search box;
  * avoid-keywords bind everywhere a *standing* preference decides the results
    (feed, subscriptions, topic browsing), and yield only to a keyword the
    learner types right now, which is a fresh explicit instruction.
"""

import json
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.content_recommender import elastic_recommender
from zeeguu.core.content_recommender.elastic_recommender import (
    article_and_video_search_for_user,
    topic_filter_for_user,
)
from zeeguu.core.elastic.elastic_query_builder import build_elastic_search_query
from zeeguu.core.model import Search, SearchFilter, UserPreference
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule

db_session = zeeguu.core.model.db.session

AVOIDED = "trump bitcoin"
DISTURBING_CLAUSE = {"match": {"is_disturbing": True}}


class FakeLanguage:
    name = "Danish"


def must_not_clauses(query):
    """
    Every clause sitting under a `must_not` anywhere in the query.

    Flattened rather than read off a fixed path because elasticsearch_dsl
    decides for itself how deep to nest a negation; what the filters promise is
    that the exclusion is *in* the query, not where it sits.
    """
    if isinstance(query, dict):
        found = []
        for key, value in query.items():
            if key == "must_not":
                found.extend(value if isinstance(value, list) else [value])
            else:
                found.extend(must_not_clauses(value))
        return found
    if isinstance(query, list):
        return [c for item in query for c in must_not_clauses(item)]
    return []


def excludes_avoided_keywords(query):
    clauses = must_not_clauses(query)
    return {"match": {"title": AVOIDED}} in clauses and {
        "match": {"content": AVOIDED}
    } in clauses


def excludes_disturbing(query):
    return DISTURBING_CLAUSE in must_not_clauses(query)


class SearchQueryBuilderTest(TestCase):
    def a_query(self, **kwargs):
        return build_elastic_search_query(20, "iran", FakeLanguage(), **kwargs)

    def test_avoided_keywords_are_excluded_when_asked_for(self):
        assert excludes_avoided_keywords(
            self.a_query(unwanted_user_searches=AVOIDED)
        )

    def test_disturbing_content_is_excluded_when_asked_for(self):
        assert excludes_disturbing(self.a_query(filter_disturbing=True))

    def test_neither_filter_is_applied_unasked(self):
        # The builder stays a builder: it is the callers above it that decide a
        # learner's settings apply, so an unparameterised call must not invent them.
        query = self.a_query()

        assert not excludes_avoided_keywords(query)
        assert not excludes_disturbing(query)

    def test_the_search_term_itself_still_selects(self):
        # A filter that also swallowed the query would "pass" every assertion above.
        assert "iran" in json.dumps(self.a_query(filter_disturbing=True))


class CapturingES:
    """Stands in for Elasticsearch so we can read the query that was built."""

    bodies = []

    def __init__(self, *args, **kwargs):
        pass

    def search(self, index=None, body=None, **kwargs):
        CapturingES.bodies.append(body)
        return {"hits": {"hits": []}}


class AvoidFiltersReachElasticsearchTest(ModelTestMixIn, TestCase):
    """
    The gap was never in the builder -- it was that
    `article_and_video_search_for_user` already *computed* the learner's avoid
    list and disturbing preference and then dropped them on the floor. So these
    go through the real function with a real user and read the query that
    actually reached Elasticsearch.
    """

    def setUp(self):
        super().setUp()
        CapturingES.bodies = []

        self.user = UserRule().user
        language_id = self.user.learned_language.id

        for keyword in AVOIDED.split():
            SearchFilter.find_or_create(
                db_session,
                self.user,
                Search.find_or_create(db_session, keyword, language_id),
            )

        UserPreference.find_or_create(
            db_session, self.user, UserPreference.FILTER_DISTURBING_CONTENT, "true"
        )

    def captured_query(self):
        assert len(CapturingES.bodies) == 1
        return CapturingES.bodies[0]

    @patch.object(elastic_recommender, "Elasticsearch", CapturingES)
    def test_a_saved_search_does_not_outrank_the_avoid_list(self):
        article_and_video_search_for_user(self.user, 1, "iran")

        assert excludes_avoided_keywords(self.captured_query())

    @patch.object(elastic_recommender, "Elasticsearch", CapturingES)
    def test_a_saved_search_does_not_outrank_the_disturbing_toggle(self):
        article_and_video_search_for_user(self.user, 1, "iran")

        assert excludes_disturbing(self.captured_query())

    @patch.object(elastic_recommender, "Elasticsearch", CapturingES)
    def test_a_typed_search_overrides_the_avoid_list_but_not_the_toggle(self):
        # Typing a word into the search box is an explicit instruction that beats
        # the standing keyword list. The safety toggle is not a preference the
        # learner is overriding here, and holds.
        article_and_video_search_for_user(
            self.user, 1, "trump", honor_avoid_keywords=False
        )

        query = self.captured_query()
        assert not excludes_avoided_keywords(query)
        assert excludes_disturbing(query)

    @patch.object(elastic_recommender, "Elasticsearch", CapturingES)
    def test_browsing_a_single_topic_honors_both_filters(self):
        topic_filter_for_user(self.user, 20, None, None, None, None, None, "politics")

        query = self.captured_query()
        assert excludes_avoided_keywords(query)
        assert excludes_disturbing(query)
