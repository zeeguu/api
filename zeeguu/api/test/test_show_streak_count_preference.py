from fixtures import LoggedInClient, logged_in_client as client


def test_show_streak_defaults_to_true_without_writing_a_row(client: LoggedInClient):
    from zeeguu.core.model import User, UserPreference

    assert client.get("/user_preferences")["show_streak_count"] == "true"

    user = User.find(client.email)
    assert UserPreference.query.filter_by(user_id=user.id, key=UserPreference.SHOW_STREAK_COUNT).count() == 0


def test_show_streak_is_saved_and_logged(client: LoggedInClient):
    from zeeguu.core.constants import EVENT_PREFERENCE_CHANGED
    from zeeguu.core.model import User, UserActivityData

    client.post("/save_user_preferences", data={"show_streak_count": "false"})
    assert client.get("/user_preferences")["show_streak_count"] == "false"

    client.post("/save_user_preferences", data={"show_streak_count": "true"})
    assert client.get("/user_preferences")["show_streak_count"] == "true"

    user = User.find(client.email)
    events = UserActivityData.query.filter_by(
        user_id=user.id, event=EVENT_PREFERENCE_CHANGED, value="show_streak_count"
    ).all()
    assert len(events) == 2


def test_show_streak_refuses_other_values(client: LoggedInClient):
    response = client.response_from_post("/save_user_preferences", data={"show_streak_count": "maybe"})
    assert response.status_code == 400
    assert client.get("/user_preferences")["show_streak_count"] == "true"
