from fixtures import logged_in_client as client, add_source_types, add_context_types
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA


def test_article_info(client):
    article_id = _create_new_article(client)

    article_info = client.get(f"/user_article?article_id={article_id}")
    print(article_info)

    assert "content" in article_info
    # The reader rebuilds past translations from these, not from a
    # "translations" list (dropped: no client has read it since Mar 2025).
    assert "tokenized_title_new" in article_info


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
    add_source_types()
    add_context_types()
    article = client.post(
        "/find_or_create_article", data=dict(url=URL_SPIEGEL_VENEZUELA)
    )
    article_id = article["id"]
    return article_id


def test_difficulty_rating_is_sent_to_the_reader_only(client):
    # The rating box is inside the reader, which loads its article through
    # /user_article; list endpoints skip the lookup.
    article_id = _create_new_article(client)
    client.post("/user_article", data=dict(article_id=article_id, starred="True"))
    client.post(
        "/article_difficulty_feedback",
        data=dict(article_id=article_id, difficulty=5),
    )

    article_info = client.get(f"/user_article?article_id={article_id}")
    assert article_info["relative_difficulty"] == 5

    listed = client.get("/user_articles/starred_or_liked")
    assert [a["id"] for a in listed] == [article_id]
    assert "relative_difficulty" not in listed[0]
