import json

from fixtures import client_with_new_user_bookmark_and_session


def test_delete(client_with_new_user_bookmark_and_session):
    client, bookmark_id, session, append_session = client_with_new_user_bookmark_and_session

    client.post(append_session(f"delete_bookmark/{bookmark_id}"))

    bookmarks = _all_bookmarks(client, append_session)
    assert len(bookmarks) == 0


def test_last_bookmark_added_is_first_in_bookmarks_by_day(client_with_new_user_bookmark_and_session):
    client, bookmark_id, session, append_session = client_with_new_user_bookmark_and_session

    bookmarks = _all_bookmarks(client, append_session)
    bookmarks_on_first_day = bookmarks[0]["bookmarks"]
    assert bookmark_id == bookmarks_on_first_day[0]["id"]


def test_contribute_own_translation(client_with_new_user_bookmark_and_session):
    client, bookmark_id, session, append_session = client_with_new_user_bookmark_and_session

    bookmark1 = _get_first_bookmark_on_day1(client, append_session)

    # WHEN
    data = dict(
        word=bookmark1["from"],
        url=bookmark1["url"],
        title=bookmark1["title"],
        context=bookmark1["context"],
        translation="companion",
    )

    client.post(append_session("contribute_translation/de/en"), data=data)

    # THEN

    bookmark = _get_first_bookmark_on_day1(client, append_session)
    assert ("companion" in str(bookmark))


def test_update_bookmark(client_with_new_user_bookmark_and_session):
    client, bookmark_id, session, append_session = client_with_new_user_bookmark_and_session

    bookmark1 = _get_first_bookmark_on_day1(client, append_session)
    bookmark1_id = bookmark1["id"]

    # WHEN
    data = dict(
        word=bookmark1["from"],
        url=bookmark1["url"],
        title=bookmark1["title"],
        context="a new context",
        translation="companion",
    )

    client.post(append_session(f"update_bookmark/{bookmark1_id}"), data=data)

    # THEN
    bookmark = _get_first_bookmark_on_day1(client, append_session)
    assert ("companion" in str(bookmark))
    assert ("a new context" in str(bookmark))


# Basic hittin of the /top_bookmarks endpoint
def test_top_bookmarks(client_with_new_user_bookmark_and_session):
    client, bookmark_id, session, append_session = client_with_new_user_bookmark_and_session

    result = client.get(append_session("/top_bookmarks/10"))
    top_bookmarks = json.loads(result.data)
    assert len(top_bookmarks) > 0


def test_context_parameter_functions_in_bookmarks_by_day(client_with_new_user_bookmark_and_session):
    client, bookmark_id, session, append_session = client_with_new_user_bookmark_and_session

    day1_bookmarks = _get_bookmarks_on_day1(client, append_session)
    assert day1_bookmarks["date"]

    some_bookmark = day1_bookmarks["bookmarks"][0]
    for key in ["from", "to", "id", "context", "title", "url"]:
        assert key in some_bookmark

    # if we don't pass the context argument, we don't get the context
    days = _get_bookmarks_by_date(client, append_session, "/bookmarks_by_day/no_context")
    day1 = days[0]
    bookmark1 = day1["bookmarks"][0]

    assert "context" not in bookmark1


def test_get_known_bookmarks_after_date(client_with_new_user_bookmark_and_session):
    # Observation here... we have /bookmarks_by_day via POST which can take more query arguments as this test shows
    def first_day_of(year):
        return str(year) + "-01-01T00:00:00"

    client, bookmark_id, session, append_session = client_with_new_user_bookmark_and_session

    form_data = dict()
    bookmarks = _get_bookmarks_by_date_via_post(client, append_session, form_data)

    # If we don't ask for the context, we don't get it
    assert "context" not in bookmarks[0]["bookmarks"][0]
    # Also, since we didn't pass any after_date we get all the three days
    assert len(bookmarks) == 1

    # # No bookmarks in the tests after 2030
    form_data["after_date"] = first_day_of(2030)
    bookmarks = _get_bookmarks_by_date_via_post(client, append_session, form_data)
    assert len(bookmarks) == 0


# # # # # # # # # # # # # # # # # Helper Functions

def _all_bookmarks(client, append_session):
    url = append_session("/bookmarks_by_day/with_context")
    result = client.get(url)
    bookmarks = json.loads(result.data)

    return bookmarks


def _get_first_bookmark_on_day1(client, append_session):
    day1 = _get_bookmarks_on_day1(client, append_session)
    return day1["bookmarks"][0]


def _get_bookmarks_by_date(client, append_session, endpoint="/bookmarks_by_day/with_context"):
    elements = json.loads(client.get(append_session(endpoint)).data)
    return elements


def _get_bookmarks_on_day1(client, append_session):
    elements = _get_bookmarks_by_date(client, append_session)
    day1 = elements[0]
    return day1


def _get_bookmarks_by_date_via_post(client, append_session, payload):
    elements = json.loads(client.post(append_session("/bookmarks_by_day"), data=payload).data)
    return elements
