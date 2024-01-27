from fixtures import logged_in_client as client, add_one_bookmark


def test_start_new_reading_session(client):
    new_reading_session = client.post("/reading_session_start", data=dict(article_id=1))
    assert new_reading_session
    assert new_reading_session["id"]
    return new_reading_session["id"]


def test_update_reading_session(client):
    session_id = test_start_new_reading_session(client)

    client.post("/reading_session_update", data=dict(id=session_id, duration=2000))

    session_info = client.get(f"/reading_session_info/{session_id}")
    assert session_info["duration"] == 2000


def test_end_reading_session(client):
    session_id = test_start_new_reading_session(client)

    result = client.post("/reading_session_end", data=dict(id=session_id))

    assert result == b"OK"
