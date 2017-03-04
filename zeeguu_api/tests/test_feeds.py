# coding=utf-8

import json
from unittest import TestCase

from api_test_mixin import APITestMixin


class FeedTests(APITestMixin, TestCase):

    def test_get_feeds_at_nonexistent_source(self):
        print "this next message is in #test_get_feeds_at_inexistent_source"
        feeds = self.json_from_api_post('/get_feeds_at_url', dict(url="http://nothinghere.is"))
        assert len(feeds) == 0

    # obtaining feeds
    def test_get_feeds_at_url(self):
        resulting_feeds = []

        urls_to_test = ["http://derspiegel.de",
                        "http://tageschau.de",
                        "http://zeit.de",
                        "http://www.handelsblatt.com"]

        for each_url in urls_to_test:
            feeds = self.json_from_api_post('/get_feeds_at_url', dict(url=each_url))
            resulting_feeds += feeds

            # following assertion makes sure that we find at least on feed
            # in each o the urls_to_test
            assert (feeds[0]["title"])

        # following assertion assumes that each site has at least one feed
        assert len(resulting_feeds) >= 4
        return resulting_feeds

    def test_start_following_feed_with_id(self):
        self.test_start_following_feed()

        response = self.api_get("stop_following_feed/1")
        assert response.data == "OK"

        print "now not following feed.let's try to follow it again!"
        form_data = {"feed_id": 1}

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
                    image="http://www.nieuws.nl/img",
                    url="http://www.nieuws.nl/rss",
                    language="nl",
                    title="Nieuws",
                    description="Description"
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
        feeds = self.test_get_feeds_at_url()
        feed_urls = [feed.get("url") for feed in feeds]

        form_data = dict(
            feeds=json.dumps(feed_urls))
        self.api_post('/start_following_feeds', form_data)

        feeds = self.json_from_api_get("get_feeds_being_followed")
        # Assumes that the derspiegel site will always have two feeds
        assert len(feeds) >= 1
        feed_count = len(feeds)
        assert feeds[0]["language"] == "de"

        # Make sure that if we call this twice, we don't get two feed entries
        self.api_post('/start_following_feeds', form_data)
        feeds = self.json_from_api_get("get_feeds_being_followed")
        assert feed_count == len(feeds)

    def test_start_following_feed(self):
        form_data = dict(
            feed_info=json.dumps(
                dict(
                    image="http://www.nieuws.nl/img",
                    url="http://www.nieuws.nl/rss",
                    language="nl",
                    title="Nieuws",
                    description="Description"
                )))
        self.api_post('/start_following_feed', form_data)

        feeds = self.json_from_api_get("get_feeds_being_followed")
        # Assumes that the derspiegel site will always have two feeds
        print feeds

    def test_stop_following_feed(self):
        self.test_start_following_feeds()
        # After this test, we will have a bunch of feeds for the user

        feeds = self.json_from_api_get("get_feeds_being_followed")
        initial_feed_count = len(feeds)

        # Now delete one
        response = self.api_get("stop_following_feed/1")
        assert response.data == "OK"

        feeds = self.json_from_api_get("get_feeds_being_followed")
        assert len(feeds) == initial_feed_count - 1

        # Now delete the second
        self.api_get("stop_following_feed/2")
        assert response.data == "OK"

        feeds = self.json_from_api_get("get_feeds_being_followed")
        assert len(feeds) == initial_feed_count - 2

    def test_show_all_clients_feeds(self):
        self.test_start_following_feeds()
        response = self.api_get("get_feeds_being_followed")
        print response.data

    def test_get_interesting_feeds(self):
        self.test_start_following_feeds()
        # After this test, we will have two feeds for the user

        interesting_feeds = self.json_from_api_get("interesting_feeds/de")
        first_feed = interesting_feeds[0]
        assert first_feed["id"]
        assert first_feed["title"]
        assert first_feed["url"]
        assert len(interesting_feeds) > 0

    def test_multiple_stop_following_same_feed(self):
        self.test_stop_following_feed()
        # After this test, we will have removed both the feeds 1 and 2

        # Now try to delete the first one more time
        response = self.api_get("stop_following_feed/1")
        assert "OOPS" in response.data

    def test_get_feed_items(self):
        self.test_start_following_feeds()
        # After this test, we will have two feeds for the user

        feed_items = self.json_from_api_get("get_feed_items/1")
        assert len(feed_items) > 0
        assert feed_items[0]["title"]
        assert feed_items[0]["summary"]
        assert feed_items[0]["published"]
