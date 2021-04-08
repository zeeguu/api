# coding=utf-8

import json
from unittest import TestCase

from zeeguu_api_test.api_test_mixin import APITestMixin

import zeeguu_core

example1_post_url = "/contribute_translation/de/en"
example1_context = "Mein Freund lächelte"
example1_context_url = "http://www.derkleineprinz-online.de/text/2-kapitel/"
example1_payload = dict(
    word="Freund",
    translation="friend",
    context=example1_context,
    url=example1_context_url,
)


class BookmarkTest(APITestMixin, TestCase):
    def setUp(self):
        super(BookmarkTest, self).setUp()

        self.example_bookmark_id = self._add_example_bookmark()

    def _add_example_bookmark(self):
        new_bookmark_id = self.json_from_api_post(example1_post_url, example1_payload)[
            "bookmark_id"
        ]
        return new_bookmark_id

    def test_last_bookmark_added_is_first_in_bookmarks_by_day(self):
        all_bookmarks = self.json_from_api_get("/bookmarks_by_day/with_context")
        bookmarks_on_first_day = all_bookmarks[0]["bookmarks"]
        assert self.example_bookmark_id == bookmarks_on_first_day[0]["id"]

    def test_context_parameter_functions_in_bookmarks_by_day(self):
        elements = self.json_from_api_get("/bookmarks_by_day/with_context")
        some_date = elements[0]
        assert some_date["date"]

        some_bookmark = some_date["bookmarks"][0]
        for key in ["from", "to", "id", "context", "title", "url"]:
            assert key in some_bookmark

        # if we don't pass the context argument, we don't get
        # the context
        elements = self.json_from_api_get("/bookmarks_by_day/no_context")
        some_date = elements[0]
        some_contrib = some_date["bookmarks"][0]
        assert not "context" in some_contrib

    #
    def test_delete_bookmark(self):
        self.api_post(f"delete_bookmark/{self.example_bookmark_id}")
        bookmarks = self.json_from_api_get("/bookmarks_by_day/with_context")
        assert len(bookmarks) == 0

    def test_upload_translation(self):
        # GIVEN
        elements = self.json_from_api_get("/bookmarks_by_day/with_context")
        day1 = elements[0]
        bookmark1 = day1["bookmarks"][0]

        # WHEN
        data = dict(
            word=bookmark1["from"],
            url=bookmark1["url"],
            title=bookmark1["title"],
            context=bookmark1["context"],
            translation="lamb",
        )

        self.api_post("contribute_translation/de/en", data)

        # THEN

        elements = self.json_from_api_get("/bookmarks_by_day/with_context")
        day1 = elements[0]
        bookmark1 = day1["bookmarks"][0]
        self.assertTrue("lamb" in str(bookmark1))

    def test_get_known_bookmarks_after_date(self):
        """
        The dates in which we have bookmarks in the test data are: 2014, 2011, 2001
        :return:
        """

        def first_day_of(year):
            return str(year) + "-01-01T00:00:00"

        form_data = dict()
        bookmarks = self.json_from_api_post("/bookmarks_by_day", form_data)
        # If we don't ask for the context, we don't get it
        assert "context" not in bookmarks[0]["bookmarks"][0]
        # Also, since we didn't pass any after_date we get all the three days
        assert len(bookmarks) == 1

        # No bookmarks in the tests after 2030
        form_data["after_date"] = first_day_of(2030)
        bookmarks = self.json_from_api_post("/bookmarks_by_day", form_data)
        assert len(bookmarks) == 0

    def test_True_and_true_both_accepted(self):
        """
        Tests that both "True" and "true" can be used as values for the "with_context" form field.
        :return:
        """

        form_data = {"with_context": "true"}
        bookmarks = self.json_from_api_post("/bookmarks_by_day", form_data)
        assert "context" in bookmarks[0]["bookmarks"][0]

        form_data = {"with_context": "True"}
        bookmarks = self.json_from_api_post("/bookmarks_by_day", form_data)
        assert "context" in bookmarks[0]["bookmarks"][0]

    def test_top_bookmarks(self):
        """
        Tests that both "True" and "true" can be used as values for the "with_context" form field.
        :return:
        """
        result = self.raw_data_from_api_get("/top_bookmarks/10")
        assert len(result) > 0
