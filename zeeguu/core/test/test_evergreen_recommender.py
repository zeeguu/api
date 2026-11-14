"""
The Evergreen tab (content_recommender/evergreen.py): only articles labeled
`general`, the learner's keywords before their topics, and on a later visit
what the learner has not seen before what they passed by.
"""

from datetime import datetime, timedelta

import zeeguu.core
from zeeguu.core.content_recommender.evergreen import evergreen_recommendations_for_user
from zeeguu.core.model import Search, UserArticle, UserPreference
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


class EvergreenRecommenderTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.language = self.user.learned_language
        self.science = TopicRule.get_or_create_topic(3)
        session.add(TopicSubscription(self.user, self.science))
        session.commit()

    def _article(self, title, article_type="general", topic=None, summary="x"):
        article = ArticleRule().article
        article.title = title
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
        self._article("Wolves are back in Jutland", summary="the ulv returns")
        self._subscribe_to_keyword("ulv")

        assert self._titles()[0] == "Wolves are back in Jutland"

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
