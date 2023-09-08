from zeeguu.api.test.fixtures import client_with_new_user_and_session


def test_set_learned_language(client_with_new_user_and_session):
    client, _, in_session = client_with_new_user_and_session

    result = client.get(in_session("/learned_language"))
    assert "de" == result.data.decode("utf-8")

    result = client.post(in_session("/learned_language/en"))
    assert "OK" == result.data.decode("utf-8")

    result = client.get(in_session("/learned_language"))
    assert "en" == result.data.decode("utf-8")
