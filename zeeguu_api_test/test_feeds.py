# coding=utf-8

from unittest import TestCase

from zeeguu_api_test.api_test_mixin import APITestMixin
from zeeguu_api.api.feeds import (
    STOP_FOLLOWING_FEED,
    FOLLOWED_FEEDS,
    START_FOLLOWING_FEED,
    INTERESTING_FEEDS,
    RECOMMENDED_FEEDS,
)

from zeeguu_core.model import RSSFeedRegistration
from zeeguu_core.content_retriever.article_downloader import download_from_feed
from zeeguu_core_test.rules.rss_feed_rule import RSSFeedRule
import zeeguu_core


class FeedTests(APITestMixin, TestCase):
    def setUp(self):
        super().setUp()

        self.feed1 = RSSFeedRule().feed1

        RSSFeedRegistration.find_or_create(
            zeeguu_core.db.session, self.user, self.feed1
        )

    def test_stop_following_feed(self):
        feed_id = self.feed1.id

        initial_feed_count = len(self.json_from_api_get(f"{FOLLOWED_FEEDS}"))

        # if we stop following one, we'll follow only one
        form_data = {"source_id": feed_id}
        assert self.api_post(f"{STOP_FOLLOWING_FEED}", form_data).data == b"OK"
        feeds = self.json_from_api_get(f"{FOLLOWED_FEEDS}")
        assert len(feeds) == initial_feed_count - 1

    def test_start_following_feed(self):
        new_feed_id = RSSFeedRule().feed.id

        # When
        form_data = {"source_id": new_feed_id}
        self.api_post(f"/{START_FOLLOWING_FEED}", form_data)

        # Then
        followed_feed_ids = [
            each["id"] for each in self.json_from_api_get(f"/{FOLLOWED_FEEDS}")
        ]
        assert new_feed_id in followed_feed_ids

    def test_get_interesting_feeds(self):
        lang_code = self.feed1.language.code
        interesting_feeds = self.json_from_api_get(f"{INTERESTING_FEEDS}/{lang_code}")
        assert len(interesting_feeds) > 0

    def test_non_subscribed_feeds(self):
        lang_code = self.feed1.language.code

        non_subscribed_feeds = self.json_from_api_get(
            f"{RECOMMENDED_FEEDS}/{lang_code}"
        )
        initial_non_subscribed_count = len(non_subscribed_feeds)

        self.test_stop_following_feed()
        non_subscribed_feeds = self.json_from_api_get(
            f"{RECOMMENDED_FEEDS}/{lang_code}"
        )
        final_non_subscribed_count = len(non_subscribed_feeds)

        assert final_non_subscribed_count > initial_non_subscribed_count

    def test_multiple_stop_following_same_feed(self):
        feed_id = self.feed1.id

        form_data = {"source_id": feed_id}
        # if we stop following one it'll be ok
        assert self.api_post(f"{STOP_FOLLOWING_FEED}", form_data).data == b"OK"

        # if we stop following it once more, not ok
        assert not (self.api_post(f"{STOP_FOLLOWING_FEED}", form_data).data == b"OK")

    def test_get_feed_items_with_metrics(self):
        download_from_feed(self.feed1, zeeguu_core.db.session, 3)

        feed_items = self.json_from_api_get(
            f"get_feed_items_with_metrics/{self.feed1.id}"
        )

        assert len(feed_items) > 0

        assert feed_items[0]["title"]
        assert feed_items[0]["summary"]
        assert feed_items[0]["published"]
        assert feed_items[0]["metrics"]
