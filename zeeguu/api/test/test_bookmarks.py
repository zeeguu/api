from fixtures import logged_in_client as client, add_context_types, add_source_types
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA


def test_create_and_delete_bookmark(client):
    add_context_types()
    add_source_types()
    from zeeguu.core.model.bookmark_context import ContextIdentifier
    from zeeguu.core.model.context_type import ContextType
    import json

    context_i = ContextIdentifier(ContextType.USER_EDITED_TEXT)
    new_bookmark = client.post(
        "/contribute_translation/de/en",
        data=dict(
            word="Freund",
            translation="friend",
            context="Mein Freund lächelte",
            url=URL_SPIEGEL_VENEZUELA,
            source_id=None,
            context_identifier=json.dumps(context_i.as_dictionary()),
        ),
    )
    assert new_bookmark
    new_bookmark_id = new_bookmark["bookmark_id"]

    bookmarks_by_day = client.post("/bookmarks_by_day")
    assert len(bookmarks_by_day) == 1

    response = client.post(f"/delete_bookmark/{new_bookmark_id}")
    assert response == b"OK"
