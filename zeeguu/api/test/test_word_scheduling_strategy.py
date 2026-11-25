"""The word scheduling strategy as a preference: /save_user_preferences."""

from zeeguu.api.test.fixtures import logged_in_client


def test_a_strategy_is_saved_by_name(logged_in_client):
    logged_in_client.post(
        "/save_user_preferences", data={"word_scheduling_strategy": "frequency_priority"}
    )
    assert logged_in_client.get("/user_preferences")["word_scheduling_strategy"] == "frequency_priority"


def test_an_unknown_strategy_is_refused(logged_in_client):
    response = logged_in_client.client.post(
        logged_in_client.append_session("/save_user_preferences"),
        data={"word_scheduling_strategy": "true"},
    )
    assert response.status_code == 400
    assert "word_scheduling_strategy" not in logged_in_client.get("/user_preferences")
