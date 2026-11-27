from fixtures import LoggedInClient, logged_in_client as client


def test_exercise_families_and_self_grade_expose_defaults_without_writing_rows(client: LoggedInClient):
    from zeeguu.core.model import User, UserPreference

    prefs = client.get("/user_preferences")
    assert prefs["exercise_families"] == "multiple_choice,typing,flashcards_meaning,flashcards_word"
    assert prefs["flashcard_self_grade"] == "false"

    user = User.find(client.email)
    for key in (UserPreference.EXERCISE_FAMILIES, UserPreference.FLASHCARD_SELF_GRADE):
        assert UserPreference.query.filter_by(user_id=user.id, key=key).count() == 0


def test_exercise_families_canonicalizes_and_persists(client: LoggedInClient):
    client.post(
        "/save_user_preferences",
        data={
            "exercise_families": "flashcards_word, flashcards_meaning, flashcards_word",
            "flashcard_self_grade": "true",
        },
    )
    prefs = client.get("/user_preferences")
    assert prefs["exercise_families"] == "flashcards_meaning,flashcards_word"
    assert prefs["flashcard_self_grade"] == "true"


def test_invalid_exercise_families_or_self_grade_is_refused(client: LoggedInClient):
    for bad in [
        {"exercise_families": ""},
        {"exercise_families": "unknown_family"},
        {"exercise_families": "typing,bogus"},
        {"flashcard_self_grade": "yes"},
    ]:
        response = client.response_from_post(
            "/save_user_preferences",
            data={**bad, "daily_goal_minutes": "20"},
        )
        assert response.status_code == 400, bad

    assert client.get("/user_preferences")["daily_goal_minutes"] != "20"
