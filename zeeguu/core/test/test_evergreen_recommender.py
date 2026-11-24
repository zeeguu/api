"""
The Evergreen tab (content_recommender/evergreen.py): only articles labeled
`general`, the learner's keywords before their topics, and on a later visit
what the learner has not seen before what they passed by.

Keywords are searched in Elasticsearch, within the pool the database chose.
FakeElasticsearch stands in for it: a match in the title or the text, and the
passage when the match is in the text.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.content_recommender import evergreen
from zeeguu.core.content_recommender.evergreen import evergreen_recommendations_for_user
from zeeguu.core.model import Article, Search, UserArticle, UserPreference
from zeeguu.core.model.article_classification import ArticleClassification
from zeeguu.core.model.article_topic_map import ArticleTopicMap, TopicOriginType
from zeeguu.core.model.evergreen_impression import EvergreenImpression
from zeeguu.core.model.search_subscription import SearchSubscription
from zeeguu.core.model.topic_subscription import TopicSubscription
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.topic_rule import TopicRule
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session

TODAY = datetime(2026, 11, 16, 10, 0)


def _find(body, key):
    """The first value under `key` anywhere in an ES query body."""
    if isinstance(body, dict):
        if key in body:
            return body[key]
        values = body.values()
    elif isinstance(body, list):
        values = body
    else:
        return None
    for value in values:
        found = _find(value, key)
        if found is not None:
            return found
    return None


class FakeElasticsearch:
    """Answers a search query from the test database: the articles among
    `terms.article_id` whose title or text contains the term."""

    def __init__(self, *args, **kwargs):
        pass

    def search(self, index=None, body=None, **kwargs):
        term = _find(body, "title")["query"].lower()
        hits = []
        for article_id in _find(body, "terms")["article_id"]:
            article = Article.find_by_id(article_id)
            text = article.get_content() or ""
            hit = {"_source": {"article_id": article_id}}
            if term in text.lower():
                if "highlight" in body:
                    hit["highlight"] = {"content": [f"... <mark>{term}</mark> ..."]}
            elif term not in (article.title or "").lower():
                continue
            hits.append(hit)
        return {"hits": {"hits": hits}}


class EvergreenRecommenderTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        es = patch.object(evergreen, "Elasticsearch", FakeElasticsearch)
        es.start()
        self.addCleanup(es.stop)
        self.user = UserRule().user
        self.language = self.user.learned_language
        self.science = TopicRule.get_or_create_topic(3)
        session.add(TopicSubscription(self.user, self.science))
        session.commit()

    def _article(
        self,
        title,
        article_type="general",
        topic=None,
        summary="x",
        published=None,
        content=None,
    ):
        article = ArticleRule().article
        if content:
            article.update_content(session, content=content, commit=False)
        article.title = title
        # A month old unless a test says otherwise, so the freshness bonus only
        # applies where a test asks for it (ArticleRule dates relative to the
        # real clock, not TODAY).
        article.published_time = published or TODAY - timedelta(days=30)
        article.summary = summary
        article.language = self.language
        article.article_type = article_type
        article.broken = 0
        session.add(article)
        if topic:
            session.add(ArticleTopicMap(article, topic, TopicOriginType.HARDSET))
        session.commit()
        return article

    def _subscribe_to_keyword(self, keyword):
        search = Search.find_or_create(session, keyword, self.language.id)
        SearchSubscription.find_or_create(session, self.user, search, False)

    def _titles(self, count=12, now=TODAY):
        articles, _ = evergreen_recommendations_for_user(
            self.user, self.language, count, now=now
        )
        return [a.title for a in articles]

    def test_only_general_articles(self):
        self._article("Why the sea is salty", topic=self.science)
        self._article("Election results tonight", article_type="news", topic=self.science)
        self._article("Not yet classified", article_type=None, topic=self.science)

        assert self._titles() == ["Why the sea is salty"]

    def test_keyword_match_ranks_above_topic_match(self):
        self._article("How stars are born", topic=self.science)
        self._article("Wolves are back in Jutland", content="Nu er en ulv set i Jylland.")
        self._subscribe_to_keyword("ulv")

        assert self._titles()[0] == "Wolves are back in Jutland"

    def test_a_keyword_match_says_which_keyword_it_matched(self):
        # for the EVERGREEN_LISTED log: which shown articles a keyword brought
        self._article("How stars are born", topic=self.science)
        self._article("Wolves are back in Jutland", content="Nu er en ulv set i Jylland.")
        self._subscribe_to_keyword("ulv")

        articles, _ = evergreen_recommendations_for_user(
            self.user, self.language, 12, now=TODAY
        )

        matched = {a.title: getattr(a, "_matched_keyword", None) for a in articles}
        assert matched == {
            "Wolves are back in Jutland": "ulv",
            "How stars are born": None,
        }

    def test_opened_articles_leave_the_tab(self):
        read = self._article("Already read", topic=self.science)
        self._article("Not read", topic=self.science)
        session.add(UserArticle(self.user, read, opened=TODAY - timedelta(days=1)))
        session.commit()

        assert self._titles() == ["Not read"]

    def test_the_next_day_unseen_articles_come_before_those_passed_by(self):
        first = self._article("Shown yesterday", topic=self.science)
        self._titles(count=1, now=TODAY - timedelta(days=1))
        assert EvergreenImpression.for_user(self.user.id).keys() == {first.id}

        self._article("Never shown", topic=self.science)
        assert self._titles(now=TODAY) == ["Never shown", "Shown yesterday"]

    def test_the_list_is_stable_within_a_day_and_flags_what_is_new(self):
        for i in range(5):
            self._article(f"Explainer {i}", topic=self.science)

        first_visit = self._titles(count=3)
        articles, new_today = evergreen_recommendations_for_user(
            self.user, self.language, 3, now=TODAY + timedelta(hours=2)
        )
        assert [a.title for a in articles] == first_visit
        assert new_today == {a.id for a in articles}

        # times_shown counts days, not page loads
        impressions = EvergreenImpression.for_user(self.user.id)
        assert {i.times_shown for i in impressions.values()} == {1}

    def test_disturbing_articles_are_left_out_when_the_learner_asked(self):
        grim = self._article("A grim history", topic=self.science)
        self._article("A cheerful history", topic=self.science)
        session.add(ArticleClassification(grim, "DISTURBING", "LLM"))
        pref = UserPreference(self.user, UserPreference.FILTER_DISTURBING_CONTENT, "true")
        session.add(pref)
        session.commit()

        assert self._titles() == ["A cheerful history"]

    def test_the_chosen_articles_come_back_whole(self):
        self._article("Long explainer", topic=self.science)
        articles, _ = evergreen_recommendations_for_user(self.user, self.language, 1, now=TODAY)
        # content was not loaded for scoring; the returned article has it
        assert articles[0].content

    def test_a_concurrent_duplicate_impression_does_not_fail(self):
        article = self._article("Shown twice at once", topic=self.science)
        session.add(EvergreenImpression(self.user.id, article.id, TODAY))
        session.commit()
        # a second request that read the impressions before the first wrote
        EvergreenImpression.record(session, self.user.id, [article.id], known={}, when=TODAY)
        assert len(EvergreenImpression.for_user(self.user.id)) == 1

    def test_reading_a_simplified_version_takes_the_original_off_the_tab(self):
        original = self._article("Read at B1", topic=self.science)
        self._article("Not read", topic=self.science)
        simplified = ArticleRule().article
        simplified.language = self.language
        simplified.parent_article_id = original.id
        session.add(simplified)
        session.add(UserArticle(self.user, simplified, opened=TODAY - timedelta(days=1)))
        session.commit()

        assert self._titles() == ["Not read"]

    def test_an_article_published_today_comes_before_older_unseen_ones(self):
        for i in range(5):
            self._article(f"Old explainer {i}", topic=self.science)
        self._article(
            "Why we see our breath", topic=self.science, published=TODAY - timedelta(hours=4)
        )

        assert self._titles(count=1) == ["Why we see our breath"]

    def test_the_freshness_bonus_ends_after_yesterday(self):
        self._article("Wolves explainer", topic=self.science)
        self._article(
            "Three days old", topic=self.science, published=TODAY - timedelta(days=3)
        )
        self._article(
            "Dated next week", topic=self.science, published=TODAY + timedelta(days=7)
        )
        self._subscribe_to_keyword("Wolves")

        # neither earns the bonus, so the keyword match leads
        assert self._titles()[0] == "Wolves explainer"

    def test_a_picked_keyword_narrows_the_list_to_its_matches(self):
        self._article("How stars are born", topic=self.science)
        self._article("Wolves are back", content="Nu er en ulv set i Jylland.")
        self._subscribe_to_keyword("ulv")

        articles, _ = evergreen_recommendations_for_user(
            self.user, self.language, 12, now=TODAY, only_keyword="ulv"
        )
        assert [a.title for a in articles] == ["Wolves are back"]

    def test_a_picked_keyword_comes_with_the_passage_where_it_occurs(self):
        self._article("Wolves are back", content="Nu er en ulv set i Jylland.")

        articles, _ = evergreen_recommendations_for_user(
            self.user, self.language, 12, now=TODAY, only_keyword="ulv"
        )
        assert articles[0]._search_snippet == "... <mark>ulv</mark> ..."

    def test_the_unfiltered_tab_asks_for_no_passage(self):
        self._article("Wolves are back", topic=self.science, content="Nu er en ulv set i Jylland.")
        self._subscribe_to_keyword("ulv")

        articles, _ = evergreen_recommendations_for_user(self.user, self.language, 12, now=TODAY)
        assert not hasattr(articles[0], "_search_snippet")

    def test_a_keyword_search_stays_within_the_general_articles(self):
        self._article("Wolves explained", content="Hvad spiser en ulv?")
        self._article("Wolf seen tonight", article_type="news", content="En ulv blev set i aftes.")

        articles, _ = evergreen_recommendations_for_user(
            self.user, self.language, 12, now=TODAY, only_keyword="ulv"
        )
        assert [a.title for a in articles] == ["Wolves explained"]

    def test_a_picked_topic_narrows_the_list_to_that_topic(self):
        culture = TopicRule.get_or_create_topic(2)
        self._article("How stars are born", topic=self.science)
        self._article("A history of painting", topic=culture)

        articles, _ = evergreen_recommendations_for_user(
            self.user, self.language, 12, now=TODAY, only_topic_id=culture.id
        )
        assert [a.title for a in articles] == ["A history of painting"]
