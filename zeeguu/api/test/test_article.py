from zeeguu.core.test.mocking_the_web import (
    URL_SPIEGEL_VENEZUELA,
    URL_FAZ_LEIGHTATHLETIK,
)
from fixtures import logged_in_client as client
from fixtures import add_context_types, add_source_types, create_and_get_article


def test_create_article(client):
    add_source_types()
    add_context_types()
    response_data = create_and_get_article(client)

    assert response_data
    assert response_data["id"] == 1
    assert "Venezuela" in response_data["title"]


def test_starred_or_liked(client):
    add_source_types()
    add_context_types()
    # No article is starred initially
    result = client.get("/user_articles/starred_or_liked")
    assert len(result) == 0

    # Star article
    article_id = client.post(
        "/find_or_create_article", dict(url=URL_FAZ_LEIGHTATHLETIK)
    )["id"]
    client.post("/user_article", data=dict(starred="True", article_id=article_id))

    # One article is starred eventually
    result = client.get("/user_articles/starred_or_liked")
    assert len(result) == 1

    # Like article
    client.post("/user_article", data=dict(liked="True", article_id=article_id))

    # Still one article is returned
    result = client.get("/user_articles/starred_or_liked")
    assert len(result) == 1
