from fixtures import client_with_new_user_bookmark_and_session


def test_delete(client_with_new_user_bookmark_and_session):
    client_get, client_post, bookmark_id = client_with_new_user_bookmark_and_session

    client_post(f"delete_bookmark/{bookmark_id}")

    bookmarks = _get_bookmarks_by_day_with_context(client_get)
    assert len(bookmarks) == 0


def test_last_bookmark_added_is_first_in_bookmarks_by_day(client_with_new_user_bookmark_and_session):
    client_get, _, bookmark_id = client_with_new_user_bookmark_and_session

    bookmarks = _get_bookmarks_by_day_with_context(client_get)
    bookmarks_on_first_day = bookmarks[0]["bookmarks"]
    assert bookmark_id == bookmarks_on_first_day[0]["id"]


def test_contribute_own_translation(client_with_new_user_bookmark_and_session):
    client_get, client_post, bookmark_id = client_with_new_user_bookmark_and_session

    all_bookmarks = _get_bookmarks_by_day_with_context(client_get)
    bookmark1 = _first_bookmark_on_day1(all_bookmarks)

    # WHEN
    data = dict(
        word=bookmark1["from"],
        url=bookmark1["url"],
        title=bookmark1["title"],
        context=bookmark1["context"],
        translation="companion",
    )

    client_post("contribute_translation/de/en", data)

    # THEN

    all_bookmarks = _get_bookmarks_by_day_with_context(client_get)
    bookmark = _first_bookmark_on_day1(all_bookmarks)
    assert ("companion" in str(bookmark))


def test_update_bookmark(client_with_new_user_bookmark_and_session):
    client_get, client_post, bookmark_id = client_with_new_user_bookmark_and_session

    all_bookmarks = _get_bookmarks_by_day_with_context(client_get)
    bookmark1 = _first_bookmark_on_day1(all_bookmarks)
    bookmark1_id = bookmark1["id"]

    # WHEN
    data = dict(
        word=bookmark1["from"],
        url=bookmark1["url"],
        title=bookmark1["title"],
        context="a new context",
        translation="companion",
    )

    client_post(f"update_bookmark/{bookmark1_id}", data)

    # THEN
    all_bookmarks = _get_bookmarks_by_day_with_context(client_get)
    bookmark = _first_bookmark_on_day1(all_bookmarks)
    assert ("companion" in str(bookmark))
    assert ("a new context" in str(bookmark))


# Basic hittin of the /top_bookmarks endpoint
def test_top_bookmarks(client_with_new_user_bookmark_and_session):
    client_get, _, _ = client_with_new_user_bookmark_and_session

    top_bookmarks = client_get("/top_bookmarks/10")
    assert len(top_bookmarks) > 0


def test_context_parameter_functions_in_bookmarks_by_day(client_with_new_user_bookmark_and_session):
    client_get, _, _ = client_with_new_user_bookmark_and_session

    all_bookmarks = _get_bookmarks_by_day_with_context(client_get)
    day1_bookmarks = _bookmarks_on_day1(all_bookmarks)
    assert day1_bookmarks["date"]

    some_bookmark = day1_bookmarks["bookmarks"][0]
    for key in ["from", "to", "id", "context", "title", "url"]:
        assert key in some_bookmark

    # if we don't pass the context argument, we don't get the context
    bookmarks_by_day = client_get("/bookmarks_by_day/no_context")
    bookmark1 = _first_bookmark_on_day1(bookmarks_by_day)

    assert "context" not in bookmark1


def test_get_known_bookmarks_after_date(client_with_new_user_bookmark_and_session):
    # Observation here... we have /bookmarks_by_day via POST which can take more query arguments as this test shows
    def first_day_of(year):
        return str(year) + "-01-01T00:00:00"

    _, client_post, _ = client_with_new_user_bookmark_and_session

    form_data = dict()
    bookmarks = client_post("/bookmarks_by_day", form_data)

    # If we don't ask for the context, we don't get it
    assert "context" not in bookmarks[0]["bookmarks"][0]
    # Also, since we didn't pass any after_date we get all the three days
    assert len(bookmarks) == 1

    # # No bookmarks in the tests after 2030
    form_data["after_date"] = first_day_of(2030)
    bookmarks = client_post("/bookmarks_by_day", form_data)
    assert len(bookmarks) == 0


# # # # # # # # # # # # # # # # # Helper Functions

def _get_bookmarks_by_day_with_context(client_get):
    return client_get("/bookmarks_by_day/with_context")


def _first_bookmark_on_day1(bookmarks_by_day):
    day1 = _bookmarks_on_day1(bookmarks_by_day)
    return day1["bookmarks"][0]


def _bookmarks_on_day1(bookmarks_by_day):
    day1 = bookmarks_by_day[0]
    return day1
