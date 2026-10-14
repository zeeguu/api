from datetime import datetime
from types import SimpleNamespace

from zeeguu.core.story_clustering import collapse_stories


class Article(SimpleNamespace):
    pass


class Video(SimpleNamespace):
    pass


def article(id, story_id=None, image=False, hour=0):
    return Article(
        id=id,
        story_id=story_id,
        img_url_id=100 + id if image else None,
        published_time=datetime(2026, 10, 14, hour),
    )


def ids(content):
    return [(type(c).__name__, c.id) for c in content]


def test_story_members_collapse_into_the_first_ones_position():
    first = article(1, hour=6)
    other = article(2, hour=8)
    republished = article(3, story_id=1, hour=12)
    assert ids(collapse_stories([first, other, republished])) == [
        ("Article", 3),
        ("Article", 2),
    ]


def test_member_with_image_wins_over_a_newer_one_without():
    with_image = article(1, image=True, hour=6)
    newer = article(2, story_id=1, hour=12)
    assert ids(collapse_stories([newer, with_image])) == [("Article", 1)]


def test_videos_never_collapse_with_articles_of_the_same_id():
    video = Video(id=1, published_time=datetime(2026, 10, 14, 9))
    assert ids(collapse_stories([article(1), video])) == [
        ("Article", 1),
        ("Video", 1),
    ]


def test_articles_without_a_story_pass_through():
    content = [article(1), article(2), article(3)]
    assert collapse_stories(content) == content


# --- with the database -------------------------------------------------------

from datetime import timedelta
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.model.article_broken_code_map import ArticleBrokenMap
from zeeguu.core.story_clustering import assign_story, story_outlets
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.url_rule import UrlRule

session = zeeguu.core.model.db.session


class StoryClusteringTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.first = ArticleRule().article
        self.later = ArticleRule().article
        self.later.published_time = self.first.published_time + timedelta(hours=2)
        self.later.language = self.first.language

    def _assign_as_same_story(self):
        with patch(
            "zeeguu.core.story_clustering._nearest_recent_article",
            return_value=(self.first.id, 0.95),
        ), patch("zeeguu.core.elastic.indexing.remove_from_index") as removed:
            assign_story(self.later, [0.1, 0.2], session)
        return removed

    def test_other_outlet_joins_the_story_and_both_are_listed(self):
        self._assign_as_same_story()

        assert self.later.story_id == self.first.id
        assert not self.later.broken
        for card in (self.first, self.later):
            outlets = story_outlets([card])[card.id]
            assert [o["id"] for o in outlets] == [self.first.id, self.later.id]

    def test_below_threshold_stays_its_own_story(self):
        with patch(
            "zeeguu.core.story_clustering._nearest_recent_article",
            return_value=(self.first.id, 0.80),
        ):
            assign_story(self.later, [0.1, 0.2], session)
        assert self.later.story_id is None

    def _same_outlet(self):
        self.later.url.domain = self.first.url.domain
        session.add(self.later)
        session.commit()

    def test_same_outlet_keeps_the_newer_and_breaks_the_older(self):
        self._same_outlet()
        removed = self._assign_as_same_story()

        assert self.first.broken and not self.later.broken
        assert ArticleBrokenMap.query.filter_by(article_id=self.first.id).first()
        removed.assert_called_once_with(self.first)
        assert story_outlets([self.later]) == {}

    def test_same_outlet_prefers_the_one_with_an_image(self):
        self._same_outlet()
        self.first.img_url = UrlRule().url
        session.add(self.first)
        session.commit()
        self._assign_as_same_story()

        assert self.later.broken and not self.first.broken
