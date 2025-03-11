from fixtures import logged_in_client as client, add_context_types, add_source_types
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA


def test_create_and_delete_bookmark(client):
    add_context_types()
    add_source_types()
    new_bookmark = client.post(
        "/contribute_translation/de/en",
        data=dict(
            word="Freund",
            translation="friend",
            context="Mein Freund lächelte",
            url=URL_SPIEGEL_VENEZUELA,
        ),
    )
    assert new_bookmark
    new_bookmark_id = new_bookmark["bookmark_id"]

    bookmarks_by_day = client.post("/bookmarks_by_day")
    assert len(bookmarks_by_day) == 1

    response = client.post(f"/delete_bookmark/{new_bookmark_id}")
    assert response == b"OK"
