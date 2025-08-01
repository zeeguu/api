from fixtures import (
    logged_in_client as client,
    add_context_types,
    add_source_types,
    create_and_get_article,
)
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA


def test_create_and_delete_bookmark(client):
    add_context_types()
    add_source_types()
    from zeeguu.core.model.context_identifier import ContextIdentifier
    from zeeguu.core.model.context_type import ContextType

    article = create_and_get_article(client)
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    new_bookmark = client.post(
        "/contribute_translation/de/en",
        json={
            "word": "hinter",
            "translation": "behind",
            "context": "stellt sich hinter Präsident",
            "url": URL_SPIEGEL_VENEZUELA,
            "source_id": article["source_id"],
            "context_identifier": context_i.as_dictionary(),
        },
    )

    assert new_bookmark
    new_bookmark_id = new_bookmark["bookmark_id"]

    bookmarks_by_day = client.post("/bookmarks_by_day")
    assert len(bookmarks_by_day) == 1

    response = client.post(f"/delete_bookmark/{new_bookmark_id}")
    assert response == b"OK"


def test_bookmark_with_context_endpoint(client):
    add_context_types()
    add_source_types()
    from zeeguu.core.model.context_identifier import ContextIdentifier
    from zeeguu.core.model.context_type import ContextType

    article = create_and_get_article(client)
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    new_bookmark = client.post(
        "/contribute_translation/de/en",
        json={
            "word": "hinter",
            "translation": "behind",
            "context": "stellt sich hinter Präsident",
            "url": URL_SPIEGEL_VENEZUELA,
            "source_id": article["source_id"],
            "context_identifier": context_i.as_dictionary(),
        },
    )

    assert new_bookmark
    new_bookmark_id = new_bookmark["bookmark_id"]

    # Test the new endpoint
    response = client.get(f"/bookmark_with_context/{new_bookmark_id}")
    
    assert response is not None
    assert "id" in response
    assert "from" in response
    assert "to" in response
    assert "from_lang" in response
    assert "context" in response
    assert "context_tokenized" in response
    assert response["id"] == new_bookmark_id
    assert response["from"] == "hinter"
    assert response["to"] == "behind"
    assert response["from_lang"] == "de"
    
    # Clean up
    client.post(f"/delete_bookmark/{new_bookmark_id}")
