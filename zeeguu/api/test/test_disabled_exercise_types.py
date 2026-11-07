"""/disabled_exercise_types: the switch for an exercise type that is broken."""
from fixtures import logged_in_client as client

MATCH = "Match_three_L1W_to_three_L2W"


def test_nothing_is_disabled_by_default(client):
    assert client.get("/disabled_exercise_types") == []


def test_lists_the_types_set_in_the_config(client, monkeypatch):
    config = client.client.application.config
    monkeypatch.setitem(config, "DISABLED_EXERCISE_TYPES", [MATCH])

    assert client.get("/disabled_exercise_types") == [MATCH]
