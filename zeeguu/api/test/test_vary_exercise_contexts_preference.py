from types import SimpleNamespace

from fixtures import LoggedInClient, logged_in_client as client


def test_vary_exercise_contexts_exposes_default_arm_without_writing_a_row(client: LoggedInClient):
    from zeeguu.core.model import User, UserPreference

    user = User.find(client.email)
    expected = "true" if UserPreference.vary_exercise_contexts_default(user) else "false"

    assert client.get("/user_preferences")["vary_exercise_contexts"] == expected
    assert (
        UserPreference.query.filter_by(
            user_id=user.id, key=UserPreference.VARY_EXERCISE_CONTEXTS
        ).count()
        == 0
    )


def test_vary_exercise_contexts_can_be_turned_on_and_off(client: LoggedInClient):
    client.post("/save_user_preferences", data={"vary_exercise_contexts": "true"})
    assert client.get("/user_preferences")["vary_exercise_contexts"] == "true"

    client.post("/save_user_preferences", data={"vary_exercise_contexts": "false"})
    assert client.get("/user_preferences")["vary_exercise_contexts"] == "false"


def test_invalid_vary_exercise_contexts_value_is_refused(client: LoggedInClient):
    from zeeguu.core.model import User, UserPreference

    response = client.response_from_post(
        "/save_user_preferences",
        data={"vary_exercise_contexts": "yes", "daily_goal_minutes": "20"},
    )
    assert response.status_code == 400
    user = User.find(client.email)
    assert (
        UserPreference.query.filter_by(
            user_id=user.id, key=UserPreference.VARY_EXERCISE_CONTEXTS
        ).count()
        == 0
    )
    assert client.get("/user_preferences")["daily_goal_minutes"] != "20"


def test_saving_over_duplicated_rows_drops_duplicates(client: LoggedInClient):
    from zeeguu.core.model import User, UserPreference
    from zeeguu.core.model.db import db

    user = User.find(client.email)
    for value in ("false", "true"):
        db.session.add(UserPreference(user, UserPreference.VARY_EXERCISE_CONTEXTS, value))
    db.session.commit()

    client.post("/save_user_preferences", data={"vary_exercise_contexts": "false"})

    assert client.get("/user_preferences")["vary_exercise_contexts"] == "false"
    user = User.find(client.email)
    assert (
        UserPreference.query.filter_by(
            user_id=user.id, key=UserPreference.VARY_EXERCISE_CONTEXTS
        ).count()
        == 1
    )


def test_random_rollout_splits_users_roughly_fifty_fifty_and_defaults_on_for_devs():
    from zeeguu.core.user_feature_toggles import _vary_exercise_contexts_default

    enabled = sum(
        1 for uid in range(1, 1001)
        if _vary_exercise_contexts_default(SimpleNamespace(id=uid, is_dev=False))
    )
    assert 450 <= enabled <= 550
    assert _vary_exercise_contexts_default(SimpleNamespace(id=1, is_dev=True)) is True
