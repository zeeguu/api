from fixtures import LoggedInClient, logged_in_client as client


def test_the_reminder_setting_and_permission_are_kept(client: LoggedInClient):
    client.post(
        "/save_user_preferences",
        data={
            "study_reminder_enabled": "true",
            "study_reminder_time": "07:30",
            "notifications_permission": "granted",
        },
    )

    preferences = client.get("/user_preferences")
    assert preferences["study_reminder_enabled"] == "true"
    assert preferences["study_reminder_time"] == "07:30"
    assert preferences["notifications_permission"] == "granted"


def test_turning_the_reminder_off_is_kept(client: LoggedInClient):
    client.post("/save_user_preferences", data={"study_reminder_enabled": "true"})
    client.post("/save_user_preferences", data={"study_reminder_enabled": "false"})

    assert client.get("/user_preferences")["study_reminder_enabled"] == "false"


def test_a_malformed_reminder_value_is_refused_and_nothing_is_saved(client: LoggedInClient):
    for key, value in [
        ("study_reminder_enabled", "yes"),
        ("study_reminder_time", "24:00"),
        ("study_reminder_time", "7:30"),
        ("notifications_permission", "maybe"),
    ]:
        response = client.response_from_post(
            "/save_user_preferences", data={key: value, "daily_goal_minutes": "20"}
        )
        assert response.status_code == 400, (key, value)

    preferences = client.get("/user_preferences")
    assert "study_reminder_time" not in preferences
    assert preferences["daily_goal_minutes"] != "20"


def test_saving_over_a_duplicated_row_works(client: LoggedInClient):
    from zeeguu.core.model import User, UserPreference
    from zeeguu.core.model.db import db

    user = User.find(client.email)
    for value in ("06:00", "06:15"):  # as two concurrent first saves can leave them
        db.session.add(UserPreference(user, "study_reminder_time", value))
    db.session.commit()

    client.post("/save_user_preferences", data={"study_reminder_time": "08:00"})

    assert client.get("/user_preferences")["study_reminder_time"] == "08:00"
    user = User.find(client.email)
    assert UserPreference.query.filter_by(user_id=user.id, key="study_reminder_time").count() == 1
