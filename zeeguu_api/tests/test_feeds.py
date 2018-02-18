# coding=utf-8

import json
from unittest import TestCase

from zeeguu_api.tests.api_test_mixin import APITestMixin

from zeeguu.content_retriever.article_downloader import download_from_feed
from tests_core_zeeguu.rules.rss_feed_rule import URL_OF_FEED_TWO, URL_OF_FEED_ONE, RSSFeedRule
import zeeguu


class FeedTests(APITestMixin, TestCase):
    def setUp(self):
        super().setUp()

    # obtaining feeds
    def test_get_feeds_at_url(self):
        resulting_feeds = []

        urls_to_test = [
            "http://www.handelsblatt.com",
            "http://www.spiegel.de/index.html"
        ]

        for each_url in urls_to_test:
            feeds = self.json_from_api_post('/get_feeds_at_url', dict(url=each_url))
            resulting_feeds += feeds

            # following assertion makes sure that we find at least on feed
            # in each o the urls_to_test
            assert (feeds[0]["title"])

        # following assertion assumes that each site has at least one feed
        assert len(resulting_feeds) >= 0
        return resulting_feeds

    def test_start_following_feed_with_id(self):
        feeds = self.test_start_following_feed()
        feed_id = feeds[0]['id']

        response = self.api_get(f"stop_following_feed/{feed_id}")
        assert response.data == b"OK"

        form_data = {"feed_id": feed_id}

        self.api_post('/start_following_feed_with_id', form_data)

        feeds = self.json_from_api_get("get_feeds_being_followed")
        assert len(feeds) == 1

    #
    # add a new feed,
    # then start following it
    def test_add_new_feed(self):
        # 1. add new feed
        form_data = dict(
            feed_info=json.dumps(
                dict(
                    image="",
                    url=URL_OF_FEED_ONE,
                    language="de",
                    title="Spiegel",
                    description="Nachrichten"
                )))
        result = self.api_post('/add_new_feed', form_data)
        new_feed_id = result.data

        # 2. start following it
        form_data = {"feed_id": new_feed_id}
        self.api_post('/start_following_feed_with_id', form_data)

        # 3. test that the feed is being followed
        feeds = self.json_from_api_get("/get_feeds_being_followed")
        assert len(feeds) == 1

    #
    def test_start_following_feeds(self):
        feed_urls = [URL_OF_FEED_ONE, URL_OF_FEED_TWO]

        form_data = dict(
            feeds=json.dumps(feed_urls))
        self.api_post('/start_following_feeds', form_data)

        feeds = self.json_from_api_get("get_feeds_being_followed")
        feed_count = len(feeds)

        assert feed_count == 2

        # If we call this endpoint again we should still have the same
        # number of registrations
        self.api_post('/start_following_feeds', form_data)
        feeds = self.json_from_api_get("get_feeds_being_followed")
        assert feed_count == len(feeds)

    def test_start_following_feed(self):
        form_data = dict(
            feed_info=json.dumps(
                dict(
                    image="",
                    url=URL_OF_FEED_TWO,
                    language="nl",
                    title="Telegraaf",
                    description="Description"
                )))
        self.api_post('/start_following_feed', form_data)

        feeds = self.json_from_api_get("get_feeds_being_followed")
        # Assumes that the derspiegel site will always have two feeds
        assert feeds
        return feeds

    def test_stop_following_two_feeds(self):
        self.test_start_following_feeds()
        # After this test, we will have a bunch of feeds for the user

        feeds = self.json_from_api_get("get_feeds_being_followed")
        initial_feed_count = len(feeds)

        # Now delete one
        response = self.api_get("stop_following_feed/1")
        assert response.data == b"OK"

        feeds = self.json_from_api_get("get_feeds_being_followed")
        assert len(feeds) == initial_feed_count - 1

        # Now delete the second
        self.api_get("stop_following_feed/2")
        assert response.data == b"OK"

        feeds = self.json_from_api_get("get_feeds_being_followed")
        assert len(feeds) == initial_feed_count - 2

    def test_show_all_clients_feeds(self):
        self.test_start_following_feeds()
        response = self.api_get("get_feeds_being_followed")
        assert response.data

    def test_get_interesting_feeds(self):
        self.test_start_following_feeds()
        # After this test, we will have two feeds for the user

        interesting_feeds = self.json_from_api_get("interesting_feeds/de")
        first_feed = interesting_feeds[0]
        assert first_feed["id"]
        assert first_feed["url"]
        assert len(interesting_feeds) > 0

    def test_non_subscribed_feeds(self):
        self.test_start_following_feeds()
        # After this test, we will have two feeds for the user

        feeds = self.json_from_api_get("get_feeds_being_followed")

        non_subscribed_feeds = self.json_from_api_get("non_subscribed_feeds/de")
        assert not non_subscribed_feeds

        self.test_stop_following_two_feeds()
        non_subscribed_feeds = self.json_from_api_get("non_subscribed_feeds/de")
        assert len(non_subscribed_feeds) == 1

    def test_multiple_stop_following_same_feed(self):
        self.test_stop_following_two_feeds()
        # After this test, we will have removed both the feeds 1 and 2

        # Now try to delete the first one more time
        response = self.api_get("stop_following_feed/1")
        assert b"OOPS" in response.data

    def test_get_feed_items_with_metrics(self):
        self.test_start_following_feeds()
        # After this test, we will have two feeds for the user

        self.spiegel = RSSFeedRule().spiegel

        download_from_feed(self.spiegel, zeeguu.db.session, 3)

        feed_items = self.json_from_api_get(f"get_feed_items_with_metrics/{self.spiegel.id}")

        assert len(feed_items) > 0

        assert feed_items[0]["title"]
        assert feed_items[0]["summary"]
        assert feed_items[0]["published"]
        assert feed_items[0]['metrics']

    def test_get_recommended_articles(self):
        from zeeguu.model import RSSFeed

        self.test_start_following_feeds()
        # After this test, we will have two feeds for the user

        self.one = RSSFeed.query.all()[0]
        self.two = RSSFeed.query.all()[1]

        download_from_feed(self.one, zeeguu.db.session, 2)
        download_from_feed(self.two, zeeguu.db.session, 3)

        feed_items = self.json_from_api_get(f"get_recommended_articles/5")
        assert (len(feed_items) == 5)
