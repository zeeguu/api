"""
Events the API logs itself (UserActivityData.log_server_event), so a study can
tell per learner and per day whether a feature was used, on every platform.
See docs/study-feature-logging.md.
"""

import json

import pytest

from fixtures import LoggedInClient, add_context_types, add_source_types
from fixtures import logged_in_client as client
from zeeguu.core.constants import PLATFORM_IOS_APP
from zeeguu.core.model import Session, User, UserActivityData, UserLanguage
from zeeguu.core.model.db import db

GERMAN_MESSAGE = (
    "Hallo zusammen! Das Training morgen fällt leider aus. Wir sehen uns am Samstag."
)


def _events(client, event):
    user = User.find(client.email)
    rows = UserActivityData.query.filter_by(user_id=user.id, event=event).order_by(
        UserActivityData.id
    )
    return [
        (row.value, json.loads(row.extra_data) if row.extra_data else None)
        for row in rows
    ]


def test_a_changed_reminder_setting_is_logged_with_before_and_after(
    client: LoggedInClient,
):
    client.post("/save_user_preferences", data={"study_reminder_enabled": "true"})
    client.post("/save_user_preferences", data={"study_reminder_enabled": "false"})

    assert _events(client, "PREFERENCE_CHANGED") == [
        ("study_reminder_enabled", {"from": None, "to": "true"}),
        ("study_reminder_enabled", {"from": "true", "to": "false"}),
    ]


def test_saving_a_setting_unchanged_logs_nothing(client: LoggedInClient):
    client.post("/save_user_preferences", data={"notifications_permission": "granted"})
    client.post("/save_user_preferences", data={"notifications_permission": "granted"})
    client.post(
        "/save_user_preferences", data={"translate_reader": "true"}
    )  # not a study setting

    assert len(_events(client, "PREFERENCE_CHANGED")) == 1


def test_the_event_carries_the_platform_of_the_login(client: LoggedInClient):
    Session.find(client.session).platform = PLATFORM_IOS_APP
    db.session.commit()

    client.post("/save_user_preferences", data={"daily_goal_minutes": "20"})

    user = User.find(client.email)
    row = UserActivityData.query.filter_by(
        user_id=user.id, event="PREFERENCE_CHANGED"
    ).one()
    assert row.value == "daily_goal_minutes"
    assert row.platform == PLATFORM_IOS_APP


def test_reaching_the_daily_goal_is_logged_once_a_day(client: LoggedInClient):
    client.post("/save_user_preferences", data={"daily_goal_minutes": "2"})
    user = User.find(client.email)
    ul = UserLanguage.find_or_create(db.session, user, user.learned_language)
    ul.last_practiced = None
    ul.daily_streak = 0
    db.session.commit()

    for seconds in (100, 130, 200):
        session_id = client.post("/browsing_session_start")["id"]
        client.post(
            "/browsing_session_update",
            data=dict(id=session_id, duration=seconds * 1000),
        )

    assert _events(client, "DAILY_GOAL_REACHED") == [
        ("de", {"goal_minutes": 2, "streak": 1})
    ]


def test_a_new_subject_for_the_daily_lessons_is_logged(client: LoggedInClient):
    client.post(
        "/configure_daily_subscription",
        data={"lesson_type": "situation", "suggestion": "ordering coffee"},
    )
    client.post(
        "/configure_daily_subscription",
        data={"lesson_type": "situation", "suggestion": "ordering coffee"},
    )
    client.post(
        "/configure_daily_subscription",
        data={"lesson_type": "topic", "suggestion": "football"},
    )

    assert _events(client, "AUDIO_LESSON_SUBJECT_SET") == [
        ("de", {"from": None, "to": ["situation", "ordering coffee"]}),
        ("de", {"from": ["situation", "ordering coffee"], "to": ["topic", "football"]}),
    ]


def test_keywords_added_and_removed_are_logged(client: LoggedInClient):
    subscription = client.get("/subscribe_search/ulv")
    client.get("/subscribe_search/ulv")  # already there
    client.post("/unsubscribe_search", data={"search_id": subscription["id"]})

    added = _events(client, "KEYWORD_ADDED")
    removed = _events(client, "KEYWORD_REMOVED")
    assert [value for value, _ in added] == ["ulv"]
    assert [value for value, _ in removed] == ["ulv"]
    assert added[0][1]["search_id"] == removed[0][1]["search_id"]


@pytest.fixture
def types(app):
    with app.app_context():
        add_source_types()
        add_context_types()


def test_a_short_text_added_and_opened_is_logged_without_its_content(
    client: LoggedInClient, types
):
    added = client.response_from_post(
        "/short_texts", data=dict(text=GERMAN_MESSAGE)
    ).json
    client.get(f"/short_texts/{added['id']}")

    expected = {"language": "de", "words": len(GERMAN_MESSAGE.split())}
    assert _events(client, "SHORT_TEXT_ADDED") == [(str(added["id"]), expected)]
    assert _events(client, "SHORT_TEXT_OPENED") == [(str(added["id"]), expected)]
    user = User.find(client.email)
    logged = " ".join(
        row.extra_data for row in UserActivityData.query.filter_by(user_id=user.id)
    )
    assert "Training" not in logged


def test_each_evergreen_listing_is_logged_with_its_filter(client: LoggedInClient):
    client.get("/user_articles/evergreen")
    client.get("/user_articles/evergreen?topic=Science")

    assert _events(client, "EVERGREEN_LISTED") == [
        ("all", {"shown": [], "new_today": [], "keyword_matches": {}}),
        ("topic:Science", {"shown": [], "new_today": [], "keyword_matches": {}}),
    ]
