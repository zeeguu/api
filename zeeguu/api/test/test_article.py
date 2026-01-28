from fixtures import logged_in_client as client
from fixtures import add_context_types, add_source_types, create_and_get_article


def test_starred_or_liked(client):
    add_source_types()
    add_context_types()
    # No article is starred initially
    result = client.get("/user_articles/starred_or_liked")
    assert len(result) == 0

    # Star article (reuse pre-loaded Spiegel article from session fixture)
    article_id = create_and_get_article(client)["id"]
    client.post("/user_article", data=dict(starred="True", article_id=article_id))

    # One article is starred eventually
    result = client.get("/user_articles/starred_or_liked")
    assert len(result) == 1

    # Like article
    client.post("/user_article", data=dict(liked="True", article_id=article_id))

    # Still one article is returned
    result = client.get("/user_articles/starred_or_liked")
    assert len(result) == 1
