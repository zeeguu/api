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
