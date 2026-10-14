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


def test_the_newest_member_gets_the_card_even_without_an_image():
    # An outlet's follow-up carries the latest news; a photo on the older
    # article must not hide it
    with_image = article(1, image=True, hour=6)
    newer = article(2, story_id=1, hour=12)
    assert ids(collapse_stories([with_image, newer])) == [("Article", 2)]


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


NEIGHBOURS = "zeeguu.core.story_clustering._nearest_recent_articles"


class StoryClusteringTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.first = ArticleRule().article
        self.later = self._article_after(self.first, hours=2)

    def _article_after(self, earlier, hours):
        article = ArticleRule().article
        article.published_time = earlier.published_time + timedelta(hours=hours)
        article.language = earlier.language
        return article

    def _assign(self, article, neighbours):
        with patch(NEIGHBOURS, return_value=neighbours), patch(
            "zeeguu.core.elastic.indexing.remove_from_index"
        ) as removed:
            assign_story(article, [0.1, 0.2], session)
        return removed

    def _assign_as_same_story(self):
        return self._assign(self.later, [(self.first.id, 0.95)])

    def _same_outlet(self, article, as_article):
        article.url.domain = as_article.url.domain
        session.add(article)
        session.commit()

    def _upload(self, article):
        article.feed = None
        session.add(article)
        session.commit()

    def test_other_outlet_joins_the_story_and_both_are_listed(self):
        self._assign_as_same_story()

        assert self.later.story_id == self.first.id
        assert not self.later.broken
        for card in (self.first, self.later):
            outlets = story_outlets([card])[card.id]
            assert [o["id"] for o in outlets] == [self.first.id, self.later.id]

    def test_below_threshold_stays_its_own_story(self):
        self._assign(self.later, [(self.first.id, 0.80)])
        assert self.later.story_id is None

    def test_a_republish_keeps_the_newer_copy_and_breaks_the_older(self):
        self._same_outlet(self.later, as_article=self.first)
        removed = self._assign_as_same_story()

        assert self.first.broken and not self.later.broken
        assert ArticleBrokenMap.query.filter_by(article_id=self.first.id).first()
        removed.assert_called_once_with(self.first)
        assert story_outlets([self.later]) == {}

    def test_a_republish_keeps_the_copy_with_an_image(self):
        self._same_outlet(self.later, as_article=self.first)
        self.first.img_url = UrlRule().url
        session.add(self.first)
        session.commit()
        self._assign_as_same_story()

        assert self.later.broken and not self.first.broken

    def test_same_outlet_follow_up_joins_the_story_and_stays_live(self):
        self._same_outlet(self.later, as_article=self.first)
        self._assign(self.later, [(self.first.id, 0.92)])

        assert self.later.story_id == self.first.id
        assert not self.first.broken and not self.later.broken

    def test_same_outlet_near_copy_a_day_later_is_not_a_republish(self):
        self.later.published_time = self.first.published_time + timedelta(hours=30)
        self._same_outlet(self.later, as_article=self.first)
        self._assign(self.later, [(self.first.id, 0.97)])

        assert self.later.story_id == self.first.id
        assert not self.first.broken and not self.later.broken

    def _dr_politiken_dr(self):
        # DR's piece, Politiken's wire copy, then DR's wire copy: the last is
        # nearest to Politiken's, with DR's own piece behind it
        politiken = self.later
        self._assign_as_same_story()
        dr_again = self._article_after(politiken, hours=1)
        self._same_outlet(dr_again, as_article=self.first)
        return politiken, dr_again

    def test_a_republish_behind_another_outlets_copy_is_still_caught(self):
        politiken, dr_again = self._dr_politiken_dr()

        self._assign(dr_again, [(politiken.id, 1.0), (self.first.id, 0.99)])

        assert dr_again.story_id == self.first.id
        assert self.first.broken and not dr_again.broken
        outlets = story_outlets([dr_again])[dr_again.id]
        assert [o["id"] for o in outlets] == [politiken.id, dr_again.id]

    def test_two_distinct_articles_of_one_outlet_are_listed_once(self):
        politiken, dr_again = self._dr_politiken_dr()

        self._assign(dr_again, [(politiken.id, 1.0), (self.first.id, 0.91)])

        assert not self.first.broken and not dr_again.broken
        outlets = story_outlets([politiken])[politiken.id]
        # DR once, by its preferred article: the newer
        assert [o["id"] for o in outlets] == [politiken.id, dr_again.id]

    def test_an_uploaded_text_never_joins_or_anchors_a_story(self):
        upload = self._article_after(self.first, hours=1)
        self._upload(upload)

        self._assign(upload, [(self.first.id, 0.95)])
        assert upload.story_id is None

        # Nearest to an upload: skip it and join the crawled one behind it
        self._assign(self.later, [(upload.id, 0.99), (self.first.id, 0.93)])
        assert self.later.story_id == self.first.id

    def test_an_uploaded_story_member_is_never_listed_as_an_outlet(self):
        self._assign_as_same_story()
        self._upload(self.later)

        assert story_outlets([self.first]) == {}
