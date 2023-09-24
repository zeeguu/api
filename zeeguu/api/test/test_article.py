import json
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA
from fixtures import client_with_new_user_and_session


def test_create_article(client_with_new_user_and_session):
    client, session, append_session = client_with_new_user_and_session

    response = client.post(
        append_session("/find_or_create_article"), data=dict(url=URL_SPIEGEL_VENEZUELA)
    )
    response_data = json.loads(response.data)
    assert response_data
    assert response_data["id"] == 1
    assert "Venezuela" in response_data["title"]
