import json
import time

from fixtures import logged_in_client as client, add_one_bookmark
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA


def test_start_new_exercise_session(client):
    new_exercise_session = client.post("/start_new_exercise_session")
    assert new_exercise_session
    assert new_exercise_session["id"]
    return new_exercise_session["id"]


def test_add_exercise_to_session(client):
    bookmark_id = add_one_bookmark(client)
    session_id = test_start_new_exercise_session(client)
    assert bookmark_id

    data = dict(
        outcome=1,
        source=1,
        solving_speed=100,
        bookmark_id=bookmark_id,
        other_feedback=1,
        session_id=session_id
    )
    new_exercise = client.post("/report_exercise_outcome",
                               data=data)
    assert b'OK' == new_exercise

    # simulate the user spending some extra time after
    # having submitted the solution
    import time
    time.sleep(2)
    client.post("/update_exercise_session", data=dict(id=1, duration=2000))

    session_info = client.get(f"/get_exercise_session/{session_id}")
    # session duration should be more than 2000
    assert (session_info['duration'] == 2000)
