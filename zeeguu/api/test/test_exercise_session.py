import json
import time

from fixtures import (
    logged_in_client as client,
    add_one_bookmark,
    add_context_types,
    add_source_types,
)
from zeeguu.core.model import User, UserExerciseSession
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA


def test_start_new_exercise_session(client):
    new_exercise_session = client.post("/exercise_session_start")
    assert new_exercise_session
    assert new_exercise_session["id"]


def test_exercise_session_captures_language_at_start(client):
    """Streak attribution must survive a later learned_language toggle, so
    the session captures the user's language at creation time."""
    session_id = client.post("/exercise_session_start")["id"]

    session = UserExerciseSession.find_by_id(session_id)
    user = User.find(client.email)
    assert session.language_id == user.learned_language_id


def test_add_exercise_to_session(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    session_id = client.post("/exercise_session_start")["id"]

    assert bookmark_id

    # Get the user_word_id from the bookmark
    from zeeguu.core.model.bookmark import Bookmark
    bookmark = Bookmark.find(bookmark_id)
    user_word_id = bookmark.user_word_id

    data = dict(
        outcome=1,
        source=1,
        solving_speed=100,
        user_word_id=user_word_id,
        other_feedback=1,
        session_id=session_id,
    )
    new_exercise = client.post("/report_exercise_outcome", data=data)
    assert b"OK" == new_exercise

    client.post("/exercise_session_update", data=dict(id=1, duration=2000))

    session_info = client.get(f"/exercise_session_info/{session_id}")
    assert session_info["duration"] == 2000


def test_practice_count_matches_practice_list(client):
    """The badge count is the length of the list the exercises get."""
    add_context_types()
    add_source_types()
    add_one_bookmark(client)

    words = client.get("/user_words_recommended_for_practice")
    count = client.get("/count_of_user_words_recommended_for_practice")
    assert count == len(words) >= 1


def _report(client, **extra):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    from zeeguu.core.model.bookmark import Bookmark

    data = dict(
        outcome="WWC",
        source=1,
        solving_speed=100,
        user_word_id=Bookmark.find(bookmark_id).user_word_id,
        session_id=client.post("/exercise_session_start")["id"],
        **extra,
    )
    return client.post("/report_exercise_outcome", data=data)


def test_wrong_answers_are_stored_in_order(client):
    from zeeguu.core.model import Exercise

    result = _report(client, wrong_answers=json.dumps(["feel sad", "  ", " unhappy "]))

    assert result == b"OK"
    exercise = Exercise.query.one()
    assert [(w.attempt_i, w.answer) for w in exercise.wrong_answers] == [
        (0, "feel sad"),
        (1, "unhappy"),
    ]


def test_malformed_wrong_answers_still_record_the_outcome(client):
    from zeeguu.core.model import Exercise, ExerciseWrongAnswer

    result = _report(client, wrong_answers="feel sad")

    assert result == b"OK"
    assert Exercise.query.count() == 1
    assert ExerciseWrongAnswer.query.count() == 0


def test_wrong_answers_are_capped(client):
    from zeeguu.core.model import ExerciseWrongAnswer

    _report(client, wrong_answers=json.dumps(["x" * 300] * 30))

    answers = ExerciseWrongAnswer.query.all()
    assert len(answers) == ExerciseWrongAnswer.MAX_PER_EXERCISE
    assert all(len(a.answer) == ExerciseWrongAnswer.MAX_LENGTH for a in answers)


def test_outcome_without_session_id_is_still_recorded(client):
    """An empty session_id (the web client posts "session_id=" before it has
    an exercise session) used to 500 and lose the answer."""
    from zeeguu.core.model.bookmark import Bookmark
    from zeeguu.core.model.exercise import Exercise

    add_context_types()
    add_source_types()
    user_word_id = Bookmark.find(add_one_bookmark(client)).user_word_id

    for session_id in ["", None]:
        data = dict(
            outcome="Correct",
            source="Recognize_L1W_in_L2T",
            solving_speed=100,
            user_word_id=user_word_id,
        )
        if session_id is not None:
            data["session_id"] = session_id
        assert b"OK" == client.post("/report_exercise_outcome", data=data)

    exercises = Exercise.query.filter_by(user_word_id=user_word_id).all()
    assert len(exercises) == 2
    assert all(e.session_id is None for e in exercises)
