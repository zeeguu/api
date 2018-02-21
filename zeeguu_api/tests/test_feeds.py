# coding=utf-8

from unittest import TestCase

from zeeguu_api.tests.api_test_mixin import APITestMixin
from zeeguu_api.api.feeds import STOP_FOLLOWING_FEED, GET_FEEDS_BEING_FOLLOWED, START_FOLLOWING_FEED_WITH_ID, \
    INTERESTING_FEEDS, NON_SUBSCRIBED_FEEDS

from zeeguu.model import RSSFeedRegistration
from zeeguu.content_retriever.article_downloader import download_from_feed
from tests_core_zeeguu.rules.rss_feed_rule import RSSFeedRule
import zeeguu


class FeedTests(APITestMixin, TestCase):
    def setUp(self):
        super().setUp()

        self.feed1 = RSSFeedRule().feed1
        self.feed2 = RSSFeedRule().feed2

        RSSFeedRegistration.find_or_create(zeeguu.db.session, self.user, self.feed1)
        RSSFeedRegistration.find_or_create(zeeguu.db.session, self.user, self.feed2)

    def test_stop_following_feed(self):
        feed_id = self.feed1.id

        initial_feed_count = len(self.json_from_api_get(f"{GET_FEEDS_BEING_FOLLOWED}"))

        # if we stop following one, we'll follow only one
        assert self.api_get(f"{STOP_FOLLOWING_FEED}/{feed_id}").data == b"OK"
        feeds = self.json_from_api_get("get_feeds_being_followed")
        assert len(feeds) == initial_feed_count - 1

    def test_start_following_feed(self):
        new_feed_id = RSSFeedRule().feed.id

        # When
        form_data = {"feed_id": new_feed_id}
        self.api_post(f'/{START_FOLLOWING_FEED_WITH_ID}', form_data)

        # Then
        followed_feed_ids = [each['id'] for each in self.json_from_api_get(f"/{GET_FEEDS_BEING_FOLLOWED}")]
        assert (new_feed_id in followed_feed_ids)

    def test_get_interesting_feeds(self):
        lang_code = self.feed1.language.code
        interesting_feeds = self.json_from_api_get(f"{INTERESTING_FEEDS}/{lang_code}")
        assert len(interesting_feeds) > 0

    def test_non_subscribed_feeds(self):
        lang_code = self.feed1.language.code

        non_subscribed_feeds = self.json_from_api_get(f"{NON_SUBSCRIBED_FEEDS}/{lang_code}")
        initial_non_subscribed_count = len(non_subscribed_feeds)

        self.test_stop_following_feed()
        non_subscribed_feeds = self.json_from_api_get(f"{NON_SUBSCRIBED_FEEDS}/{lang_code}")
        final_non_subscribed_count = len(non_subscribed_feeds)

        assert final_non_subscribed_count > initial_non_subscribed_count

    def test_multiple_stop_following_same_feed(self):
        feed_id = self.feed1.id

        # if we stop following one it'll be ok
        assert self.api_get(f"{STOP_FOLLOWING_FEED}/{feed_id}").data == b"OK"

        # if we stop following it once more, not ok
        assert not (self.api_get(f"{STOP_FOLLOWING_FEED}/{feed_id}").data == b"OK")

    def test_get_feed_items_with_metrics(self):
        download_from_feed(self.feed1, zeeguu.db.session, 3)

        feed_items = self.json_from_api_get(f"get_feed_items_with_metrics/{self.feed1.id}")

        assert len(feed_items) > 0

        assert feed_items[0]["title"]
        assert feed_items[0]["summary"]
        assert feed_items[0]["published"]
        assert feed_items[0]['metrics']

    def test_get_recommended_articles(self):
        download_from_feed(self.feed1, zeeguu.db.session, 2)
        download_from_feed(self.feed2, zeeguu.db.session, 3)

        feed_items = self.json_from_api_get(f"get_recommended_articles/5")
        assert (len(feed_items) == 5)
