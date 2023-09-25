from fixtures import logged_in_client as client
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA


def test_article_info(client):
    article_id = _create_new_article(client)

    article_info = client.get(f"/user_article?article_id={article_id}")
    print(article_info)

    assert "content" in article_info
    assert "translations" in article_info


def test_article_update(client):
    # Article is not starred initially
    article_id = _create_new_article(client)

    article_info = client.get(f"/user_article?article_id={article_id}")
    assert not article_info["starred"]

    # Make starred
    client.post(f"/user_article", data=dict(article_id=article_id, starred="True"))

    # Article should be starred
    article_info = client.get(f"/user_article?article_id={article_id}")
    assert article_info["starred"]

    # Make liked
    client.post(f"/user_article", data=dict(article_id=article_id, liked="True"))

    # Article should be both liked and starred
    article_info = client.get(f"/user_article?article_id={article_id}")
    assert article_info["starred"]
    assert article_info["liked"]

    # Un-star
    client.post(f"/user_article", data=dict(article_id=article_id, starred="False"))

    # Article is not starred anymore
    article_info = client.get(f"/user_article?article_id={article_id}")
    assert not article_info["starred"]


def _create_new_article(client):
    article = client.post("/find_or_create_article", data=dict(url=URL_SPIEGEL_VENEZUELA))
    article_id = article["id"]
    return article_id
