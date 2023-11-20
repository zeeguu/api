from fixtures import logged_in_client as client


def test_set_learned_language(client):
    result = client.get("/learned_language")
    assert "de" == result.decode("utf-8")

    result = client.post("/learned_language/en")
    assert "OK" == result.decode("utf-8")

    result = client.get("/learned_language")
    assert "en" == result.decode("utf-8")
