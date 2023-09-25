from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA, URL_FAZ_LEIGHTATHLETIK
from fixtures import logged_in_client as client


def test_create_article(client):
    response_data = client.post("/find_or_create_article", data=dict(url=URL_SPIEGEL_VENEZUELA))

    assert response_data
    assert response_data["id"] == 1
    assert "Venezuela" in response_data["title"]


def test_starred_or_liked(client):
    # No article is starred initially
    result = client.get(f"/user_articles/starred_or_liked")
    assert len(result) == 0

    # Star article
    article_id = client.post("/find_or_create_article", dict(url=URL_FAZ_LEIGHTATHLETIK))["id"]
    client.post(f"/user_article", data=dict(starred="True", article_id=article_id))

    # One article is starred eventually
    result = client.get(f"/user_articles/starred_or_liked")
    assert len(result) == 1

    # Like article
    client.post(f"/user_article", data=dict(liked="True", article_id=article_id))

    # Still one article is returned
    result = client.get(f"/user_articles/starred_or_liked")
    assert len(result) == 1
