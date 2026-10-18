"""
Endpoints that take the id of a bookmark, user word, activity session or
notification only act on objects of the current user. Somebody else's id
gets the same answer as an id that does not exist.
"""

from json import loads
from unittest.mock import patch

import pytest

from fixtures import (
    logged_in_client as client,
    LoggedInClient,
    add_one_bookmark,
    add_context_types,
    add_source_types,
)
from zeeguu.core.model import Bookmark, User
from zeeguu.core.model.db import db


@pytest.fixture
def stranger(app):
    return LoggedInClient(
        app.test_client(), email="stranger@mir.lu", username="stranger"
    )


def _bookmark(client):
    add_context_types()
    add_source_types()
    return add_one_bookmark(client)


def _update_data(context):
    return {
        "word": "hinter",
        "translation": "beyond",
        "context": context,
        "context_identifier": {"context_type": "ArticleTitle"},
    }


def test_update_bookmark_refuses_another_users_bookmark(client, stranger):
    bookmark_id = _bookmark(client)

    response = stranger.response_from_post(
        f"/update_bookmark/{bookmark_id}", json=_update_data("hinter den Horizon")
    )

    assert response.status_code == 404
    assert b"stellt sich" not in response.data
    bookmark = Bookmark.find(bookmark_id)
    assert bookmark.user_word.meaning.translation.content == "behind"
    assert bookmark.get_context() == "stellt sich hinter Präsident"


def test_update_bookmark_missing_and_foreign_look_the_same(client, stranger):
    bookmark_id = _bookmark(client)

    foreign = stranger.response_from_post(
        f"/update_bookmark/{bookmark_id}", json=_update_data("x")
    )
    missing = stranger.response_from_post(
        "/update_bookmark/999999", json=_update_data("x")
    )

    assert foreign.status_code == missing.status_code == 404
    assert foreign.data == missing.data


def test_update_bookmark_translation_missing_and_foreign_look_the_same(
    client, stranger
):
    bookmark_id = _bookmark(client)

    foreign = stranger.response_from_post(
        f"/update_bookmark_translation/{bookmark_id}", json={"translation": "x"}
    )
    missing = stranger.response_from_post(
        "/update_bookmark_translation/999999", json={"translation": "x"}
    )

    assert foreign.status_code == missing.status_code == 404
    assert foreign.data == missing.data


def test_owner_can_still_update_bookmark(client):
    bookmark_id = _bookmark(client)

    response = client.response_from_post(
        f"/update_bookmark/{bookmark_id}",
        json=_update_data("stellt sich hinter Präsident"),
    )

    assert response.status_code == 200
    assert Bookmark.find(bookmark_id).user_word.meaning.translation.content == "beyond"


def _outcome(user_word_id, session_id):
    return dict(
        outcome="C",
        source="Recognize",
        solving_speed="100",
        user_word_id=user_word_id,
        other_feedback="",
        session_id=session_id,
    )


def test_report_exercise_outcome_refuses_another_users_word(client, stranger):
    from zeeguu.core.model.exercise import Exercise

    user_word_id = Bookmark.find(_bookmark(client)).user_word_id
    session_id = stranger.post("/exercise_session_start")["id"]

    result = stranger.post(
        "/report_exercise_outcome", data=_outcome(user_word_id, session_id)
    )

    assert result == b"FAIL - UserWord not found"
    assert Exercise.query.count() == 0


def test_owner_can_still_report_exercise_outcome(client):
    user_word_id = Bookmark.find(_bookmark(client)).user_word_id
    session_id = client.post("/exercise_session_start")["id"]

    result = client.post(
        "/report_exercise_outcome", data=_outcome(user_word_id, session_id)
    )

    assert result == b"OK"


def test_similar_words_refuses_another_users_bookmark(client, stranger):
    bookmark_id = _bookmark(client)

    response = stranger.client.get(
        stranger.append_session(f"/similar_words/{bookmark_id}")
    )

    assert response.status_code == 404


def test_owner_can_still_get_similar_words(client):
    bookmark_id = _bookmark(client)

    # The test word-frequency mock cannot supply distinct random words
    with patch(
        "zeeguu.api.endpoints.exercises.similar_words", return_value=["a", "b"]
    ):
        response = client.client.get(
            client.append_session(f"/similar_words/{bookmark_id}")
        )

    assert response.status_code == 200
    assert loads(response.data) == ["a", "b"]


def test_report_exercise_issue_refuses_another_users_bookmark(client, stranger):
    bookmark_id = _bookmark(client)

    response = stranger.response_from_post(
        "/report_exercise_issue",
        json=dict(bookmark_id=bookmark_id, exercise_source="Recognize", reason="other"),
    )

    assert response.status_code == 404


def test_owner_can_still_report_exercise_issue(client):
    bookmark_id = _bookmark(client)

    result = client.post(
        "/report_exercise_issue",
        json=dict(bookmark_id=bookmark_id, exercise_source="Recognize", reason="other"),
    )

    assert result["success"]


@pytest.mark.parametrize(
    "route,status", [("star_bookmark", 404), ("delete_bookmark", 200)]
)
def test_bookmark_routes_answer_foreign_like_missing(client, stranger, route, status):
    bookmark_id = _bookmark(client)

    foreign = stranger.response_from_post(f"/{route}/{bookmark_id}")
    missing = stranger.response_from_post(f"/{route}/999999")

    assert foreign.status_code == missing.status_code == status
    assert foreign.data == missing.data
    assert Bookmark.query.get(bookmark_id) is not None
    assert not Bookmark.find(bookmark_id).starred


def test_owner_can_still_star_bookmark(client):
    bookmark_id = _bookmark(client)

    assert client.post(f"/star_bookmark/{bookmark_id}") == b"OK"
    db.session.expire_all()
    assert Bookmark.find(bookmark_id).starred


# --- activity sessions -------------------------------------------------------

_SESSION_KINDS = [
    ("reading", dict(article_id=1)),
    ("exercise", dict()),
    ("browsing", dict()),
    ("listening", None),
    ("watching", None),
]


def _start(client, kind, start_data):
    return client.post(f"/{kind}_session_start", data=start_data)["id"]


def _session_class(kind):
    from zeeguu.core.model import (
        UserReadingSession,
        UserExerciseSession,
        UserBrowsingSession,
        UserListeningSession,
    )
    from zeeguu.core.model.user_watching_session import UserWatchingSession

    return dict(
        reading=UserReadingSession,
        exercise=UserExerciseSession,
        browsing=UserBrowsingSession,
        listening=UserListeningSession,
        watching=UserWatchingSession,
    )[kind]


def _create_session_directly(client, kind):
    # Listening and watching sessions need a lesson / video to start through
    # the API; the ownership check does not care what they point to.
    from datetime import datetime

    user = User.find(client.email)
    session = _session_class(kind)(user.id, None, datetime.now())
    db.session.add(session)
    db.session.commit()
    return session.id


def _owned_session(client, kind, start_data):
    if start_data is None:
        return _create_session_directly(client, kind)
    return _start(client, kind, start_data)


@pytest.mark.parametrize("kind,start_data", _SESSION_KINDS)
@pytest.mark.parametrize("action", ["update", "end"])
def test_session_update_and_end_refuse_another_users_session(
    client, stranger, kind, start_data, action
):
    session_id = _owned_session(client, kind, start_data)

    response = stranger.response_from_post(
        f"/{kind}_session_{action}", data=dict(id=session_id, duration=999000)
    )

    assert response.status_code == 404
    db.session.expire_all()
    session = _session_class(kind).query.get(session_id)
    assert session is not None
    assert session.duration != 999000


@pytest.mark.parametrize("kind,start_data", _SESSION_KINDS)
def test_owner_can_still_update_session(client, kind, start_data):
    session_id = _owned_session(client, kind, start_data)

    response = client.response_from_post(
        f"/{kind}_session_update", data=dict(id=session_id, duration=2000)
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "kind,start_data", [k for k in _SESSION_KINDS if k[0] != "watching"]
)
def test_session_info_refuses_another_users_session(client, stranger, kind, start_data):
    session_id = _owned_session(client, kind, start_data)

    foreign = stranger.client.get(
        stranger.append_session(f"/{kind}_session_info/{session_id}")
    )
    missing = stranger.client.get(stranger.append_session(f"/{kind}_session_info/999999"))
    own = client.client.get(client.append_session(f"/{kind}_session_info/{session_id}"))

    assert foreign.status_code == missing.status_code == 404
    assert own.status_code == 200


# --- notifications -------------------------------------------------------------


def _notification_for(client):
    from zeeguu.core.model.notification import Notification
    from zeeguu.core.model.user_notification import UserNotification

    notification = Notification()
    notification.type = "EXERCISE_AVAILABLE"
    db.session.add(notification)
    db.session.flush()
    user_notification = UserNotification(User.find(client.email).id, notification.id)
    db.session.add(user_notification)
    db.session.commit()
    return user_notification.id


def test_notification_click_refuses_another_users_notification(client, stranger):
    from zeeguu.core.model.user_notification import UserNotification

    user_notification_id = _notification_for(client)

    response = stranger.response_from_post(
        "/set_notification_click_date",
        data=dict(user_notification_id=user_notification_id),
    )

    assert response.status_code == 404
    db.session.expire_all()
    assert UserNotification.query.get(user_notification_id).notification_click_time is None


def test_owner_can_still_click_notification(client):
    user_notification_id = _notification_for(client)

    result = client.post(
        "/set_notification_click_date",
        data=dict(user_notification_id=user_notification_id),
    )

    assert result == b"OK"
