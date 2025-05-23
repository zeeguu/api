from fixtures import (
    logged_in_client as client,
    add_one_bookmark,
    add_context_types,
    add_source_types,
)


def test_delete(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    client.post(f"delete_bookmark/{bookmark_id}")

    bookmarks = _get_bookmarks_by_day(client)
    assert bookmarks is not []


def test_last_bookmark_added_is_first_in_bookmarks_by_day(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)

    bookmarks = _get_bookmarks_by_day(client)
    bookmarks_on_first_day = bookmarks[0]["bookmarks"]
    assert bookmark_id == bookmarks_on_first_day[0]["id"]


def test_contribute_own_translation(client):

    add_context_types()
    add_source_types()
    bid = add_one_bookmark(client)
    all_bookmarks = _get_bookmarks_by_day(client)
    bookmark1 = _first_bookmark_on_day1(all_bookmarks)

    data = {
        "word": bookmark1["from"],
        "url": bookmark1["url"],
        "title": bookmark1["title"],
        "context": bookmark1["context"],
        "translation": "companion",
        "context_identifier": bookmark1["context_identifier"],
    }

    client.post(f"update_bookmark/{bid}", json=data)

    # THEN

    all_bookmarks = _get_bookmarks_by_day(client)
    bookmark = _first_bookmark_on_day1(all_bookmarks)
    assert "companion" in str(bookmark)


def test_update_bookmark(client):
    add_context_types()
    add_source_types()
    _ = add_one_bookmark(client)

    all_bookmarks = _get_bookmarks_by_day(client)
    bookmark1 = _first_bookmark_on_day1(all_bookmarks)
    bookmark1_id = bookmark1["id"]
    # WHEN
    data = {
        "word": bookmark1["from"],
        "url": bookmark1["url"],
        "title": bookmark1["title"],
        "context": "hinter den Horizon",
        "translation": "beyond",
        "context_identifier": bookmark1["context_identifier"],
    }

    client.post(f"update_bookmark/{bookmark1_id}", json=data)

    # THEN
    all_bookmarks = _get_bookmarks_by_day(client)
    bookmark = _first_bookmark_on_day1(all_bookmarks)

    assert "beyond" == bookmark["to"]
    assert "hinter den Horizon" == bookmark["context"]


# Basic hitting of the /top_bookmarks endpoint
def test_top_bookmarks(client):
    add_context_types()
    add_source_types()
    _ = add_one_bookmark(client)

    top_bookmarks = client.get("/top_bookmarks/10")
    assert top_bookmarks is not []


def test_context_parameter_functions_in_bookmarks_by_day(client):
    add_context_types()
    add_source_types()
    _ = add_one_bookmark(client)

    all_bookmarks = _get_bookmarks_by_day(client)
    day1_bookmarks = _bookmarks_on_day1(all_bookmarks)
    assert day1_bookmarks["date"]

    some_bookmark = day1_bookmarks["bookmarks"][0]
    for key in ["from", "to", "id", "context", "title"]:
        assert key in some_bookmark

    # if we don't pass the context argument, we don't get the context
    bookmarks_by_day = _get_bookmarks_by_day(client, with_context=False)
    bookmark1 = _first_bookmark_on_day1(bookmarks_by_day)

    assert "context" not in bookmark1


def test_get_known_bookmarks_after_date(client):
    add_context_types()
    add_source_types()

    # Observation here... we have /bookmarks_by_day via POST which can take more query arguments as this test shows
    def first_day_of(year):
        return str(year) + "-01-01T00:00:00"

    _ = add_one_bookmark(client)

    form_data = dict()
    bookmarks = client.post("/bookmarks_by_day", data=form_data)

    # If we don't ask for the context, we don't get it
    assert "context" not in bookmarks[0]["bookmarks"][0]
    # Also, since we didn't pass any after_date we get all the three days
    assert len(bookmarks) == 1

    # # No bookmarks in the tests after 2030
    form_data["after_date"] = first_day_of(2030)
    bookmarks = client.post("/bookmarks_by_day", data=form_data)
    assert bookmarks is not []


# # # # # # # # # # # # # # # # # Helper Functions


def _get_bookmarks_by_day(client, with_context=True):
    if with_context:
        return client.post(
            "/bookmarks_by_day", {"with_context": str(with_context).lower()}
        )
    else:
        return client.post("/bookmarks_by_day")


def _first_bookmark_on_day1(bookmarks_by_day):
    day1 = _bookmarks_on_day1(bookmarks_by_day)
    return day1["bookmarks"][0]


def _bookmarks_on_day1(bookmarks_by_day):
    day1 = bookmarks_by_day[0]
    return day1
