import json

from zeeguu.api.test.fixtures import client_with_new_user_and_session


def test_create_and_delete_bookmark(client_with_new_user_and_session):
    client, _, append_session = client_with_new_user_and_session

    response = client.post(
        append_session("/contribute_translation/de/en"),
        data=dict(
            word="Freund",
            translation="friend",
            context="Mein Freund lächelte",
            url="http://www.derkleineprinz-online.de/text/2-kapitel/",
        ),
    )

    response_data = json.loads(response.data)
    assert response_data
    new_bookmark_id = response_data["bookmark_id"]

    response = client.get(append_session("/bookmarks_by_day/with_context"))
    response_data = json.loads(response.data)
    assert len(response_data) == 1

    response = client.get(append_session(f"/delete_bookmark/{new_bookmark_id}"))
    print(response.data)
