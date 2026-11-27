from fixtures import LoggedInClient, logged_in_client as client


def test_exercise_families_and_self_grade_expose_defaults_without_writing_rows(client: LoggedInClient):
    from zeeguu.core.model import User, UserPreference

    prefs = client.get("/user_preferences")
    assert prefs["exercise_families"] == "multiple_choice,typing,flashcards_meaning,flashcards_word"
    assert prefs["flashcard_self_grade"] == "false"

    user = User.find(client.email)
    for key in (UserPreference.EXERCISE_FAMILIES, UserPreference.FLASHCARD_SELF_GRADE):
        assert UserPreference.query.filter_by(user_id=user.id, key=key).count() == 0


def test_exercise_families_canonicalizes_persists_and_logs_only_real_changes(client: LoggedInClient):
    from zeeguu.core.constants import EVENT_PREFERENCE_CHANGED
    from zeeguu.core.model import User, UserActivityData

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

    # Re-posting the same family set in another order does not log a duplicate change
    client.post(
        "/save_user_preferences",
        data={"exercise_families": "flashcards_word,flashcards_meaning"},
    )
    user = User.find(client.email)
    family_events = UserActivityData.query.filter_by(
        user_id=user.id, event=EVENT_PREFERENCE_CHANGED, value="exercise_families"
    ).all()
    assert len(family_events) == 1

    # Turning self-grade back off works
    client.post("/save_user_preferences", data={"flashcard_self_grade": "false"})
    assert client.get("/user_preferences")["flashcard_self_grade"] == "false"


def test_invalid_exercise_families_or_self_grade_is_refused(client: LoggedInClient):
    for bad in [
        {"exercise_families": ""},
        {"exercise_families": " , "},
        {"exercise_families": "unknown_family"},
        {"exercise_families": "typing,bogus"},
        {"flashcard_self_grade": ""},
        {"flashcard_self_grade": "yes"},
    ]:
        response = client.response_from_post(
            "/save_user_preferences",
            data={**bad, "daily_goal_minutes": "20"},
        )
        assert response.status_code == 400, bad

    assert client.get("/user_preferences")["daily_goal_minutes"] != "20"


def test_saving_over_duplicate_rows_and_exercise_source_duplicates(client: LoggedInClient):
    from zeeguu.core.model import ExerciseSource, User, UserPreference
    from zeeguu.core.model.db import db

    user = User.find(client.email)
    for value in ("typing", "multiple_choice"):
        db.session.add(UserPreference(user, UserPreference.EXERCISE_FAMILIES, value))
    db.session.commit()

    client.post("/save_user_preferences", data={"exercise_families": "flashcards_meaning"})
    assert client.get("/user_preferences")["exercise_families"] == "flashcards_meaning"
    user = User.find(client.email)
    assert (
        UserPreference.query.filter_by(user_id=user.id, key=UserPreference.EXERCISE_FAMILIES).count()
        == 1
    )

    # Duplicate ExerciseSource rows (from a first-deploy race) do not break find_or_create
    first = ExerciseSource("Flashcard_L1W_from_L2W")
    second = ExerciseSource("Flashcard_L1W_from_L2W")
    db.session.add_all([first, second])
    db.session.commit()
    found = ExerciseSource.find_or_create(db.session, "Flashcard_L1W_from_L2W")
    assert found.id == first.id
