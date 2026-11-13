"""/disable_mwe_grouping, behind "Ungroup expression" in the reader."""
from fixtures import logged_in_client as client, create_and_get_article
from zeeguu.core.model.user_mwe_override import UserMweOverride

SENTENCE = 'at Rasmus Wallbridge blev " offentligt ydmyget i månedsvis " .'


def _ungroup(client, **extra):
    article = create_and_get_article(client)
    payload = dict(
        article_id=article["id"],
        mwe_expression="blev offentligt ydmyget",
        sentence_text=SENTENCE,
        **extra,
    )
    response = client.client.post(client.append_session("/disable_mwe_grouping"), json=payload)
    return article, response


def test_a_separated_expression_ungroups_without_a_bookmark(client):
    # A separated MWE gets no bookmark when translated (get_one_translation),
    # so the reader has no bookmark id to send. Ungrouping must still stick.
    article, response = _ungroup(client)
    assert response.status_code == 200
    assert response.json["success"] is True

    stored = UserMweOverride.query.filter_by(article_id=article["id"]).all()
    assert [o.mwe_expression for o in stored] == ["blev offentligt ydmyget"]
    assert stored[0].sentence_hash == UserMweOverride.compute_sentence_hash(SENTENCE)


def test_missing_the_expression_is_still_a_400(client):
    article = create_and_get_article(client)
    response = client.client.post(
        client.append_session("/disable_mwe_grouping"),
        json=dict(article_id=article["id"], sentence_text=SENTENCE),
    )
    assert response.status_code == 400
