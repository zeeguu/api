"""/explain_selection refuses bad input as a client error."""
from fixtures import logged_in_client as client


def test_an_unknown_language_code_is_a_400(client):
    response = client.client.post(
        client.append_session("/explain_selection/xx/en"),
        json={"selection": "hinter", "context": "stellt sich hinter Präsident"},
    )
    assert response.status_code == 400
