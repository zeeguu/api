"""
A typed search matches the title or the text of an article. When the match is
in the text only, the card looked unrelated to the search ("macron", and no
Macron in the title), so the search endpoint asks Elasticsearch for the passage
where the terms occur and sends it as `search_snippet`.
"""

from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.content_recommender import elastic_recommender
from zeeguu.core.content_recommender.elastic_recommender import (
    article_and_video_search_for_user,
    get_user_info_from_content_recommendations,
)
from zeeguu.core.elastic.elastic_query_builder import build_elastic_search_query
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.user_rule import UserRule

SNIPPET = "Præsident <mark>Macron</mark> besøgte i går København."


class FakeLanguage:
    name = "Danish"


class SnippetQueryTest(TestCase):
    def test_a_typed_search_asks_for_a_passage_of_the_text(self):
        query = build_elastic_search_query(20, "macron", FakeLanguage(), with_snippets=True)

        assert list(query["highlight"]["fields"]) == ["content"]

    def test_other_searches_do_not(self):
        # The saved-search injection and the emails show no passage.
        query = build_elastic_search_query(20, "macron", FakeLanguage())

        assert "highlight" not in query


def fake_es_answering(hits):
    class FakeES:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, index=None, body=None, **kwargs):
            return {"hits": {"hits": hits}}

    return FakeES


class SnippetReachesTheCardTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.with_match = ArticleRule().article
        self.title_only = ArticleRule().article

    def search(self, **kwargs):
        hits = [
            {
                "_source": {"article_id": self.with_match.id},
                "highlight": {"content": [SNIPPET]},
            },
            # A match in the title alone: no_match_size 0 means no passage.
            {"_source": {"article_id": self.title_only.id}},
        ]
        with patch.object(elastic_recommender, "Elasticsearch", fake_es_answering(hits)):
            found = article_and_video_search_for_user(
                self.user, 20, "macron", honor_avoid_keywords=False, **kwargs
            )
        infos = get_user_info_from_content_recommendations(self.user, found)
        return {each["id"]: each for each in infos}

    def test_the_passage_is_sent_with_the_article(self):
        infos = self.search(with_snippets=True)

        assert infos[self.with_match.id]["search_snippet"] == SNIPPET

    def test_a_title_match_has_no_passage(self):
        infos = self.search(with_snippets=True)

        assert "search_snippet" not in infos[self.title_only.id]

    def test_no_passage_unless_asked_for(self):
        infos = self.search()

        assert "search_snippet" not in infos[self.with_match.id]


class PoolQueryTest(TestCase):
    def test_the_evergreen_pool_narrows_the_search_to_its_articles(self):
        query = build_elastic_search_query(20, "ulv", FakeLanguage(), only_article_ids=[3, 5])

        assert {"terms": {"article_id": [3, 5]}} in query["query"]["function_score"]["query"]["bool"]["filter"]
