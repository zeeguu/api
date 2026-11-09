import datetime

from fixtures import LoggedInClient, logged_in_client as client
from zeeguu.core.model import User, UserLanguage
from zeeguu.core.model.db import db
from zeeguu.core.util.time import server_now


def _streaks_by_code(client: LoggedInClient):
    return {each["code"]: each for each in client.get("/all_language_streaks")}


def test_last_practiced_date_is_the_users_local_day(client: LoggedInClient):
    user = User.find(client.email)
    ul = UserLanguage.find_or_create(db.session, user, user.learned_language)
    ul.last_practiced = server_now() - datetime.timedelta(days=3)
    db.session.commit()
    code = user.learned_language.code
    expected = ul.local_last_practiced.isoformat()

    entry = _streaks_by_code(client)[code]

    assert entry["last_practiced_date"] == expected
    assert "T" not in entry["last_practiced_date"]


def test_last_practiced_date_is_null_for_a_language_never_practiced(client: LoggedInClient):
    user = User.find(client.email)
    ul = UserLanguage.find_or_create(db.session, user, user.learned_language)
    ul.last_practiced = None
    db.session.commit()
    code = user.learned_language.code

    assert _streaks_by_code(client)[code]["last_practiced_date"] is None


def _never_practiced(client, goal_minutes=2):
    client.post("/save_user_preferences", data={"daily_goal_minutes": str(goal_minutes)})
    user = User.find(client.email)
    ul = UserLanguage.find_or_create(db.session, user, user.learned_language)
    ul.last_practiced = None
    ul.daily_streak = 0
    db.session.commit()
    return user.learned_language.code


def _browse(client, seconds):
    session_id = client.post("/browsing_session_start")["id"]
    client.post("/browsing_session_update", data=dict(id=session_id, duration=seconds * 1000))
    return session_id


def test_short_sessions_add_up_to_the_days_streak(client: LoggedInClient):
    code = _never_practiced(client)

    assert _streaks_by_code(client)[code]["ms_to_streak"] == 120_000

    _browse(client, 45)
    entry = _streaks_by_code(client)[code]
    assert entry["practiced_today"] is False
    assert entry["ms_to_streak"] == 75_000

    _browse(client, 80)
    entry = _streaks_by_code(client)[code]
    assert entry["practiced_today"] is True
    assert entry["daily_streak"] == 1
    assert entry["ms_to_streak"] == 0


def test_study_time_from_yesterday_does_not_count_today(client: LoggedInClient):
    from zeeguu.core.model.user_browsing_session import UserBrowsingSession

    code = _never_practiced(client)
    user = User.find(client.email)
    yesterday = UserBrowsingSession._create_new_session(
        db.session,
        user.id,
        current_time=server_now() - datetime.timedelta(days=1),
        language_id=user.learned_language_id,
    )
    yesterday.duration = 100_000
    yesterday.last_action_time = yesterday.start_time + datetime.timedelta(minutes=2)
    db.session.commit()

    _browse(client, 30)

    assert _streaks_by_code(client)[code]["practiced_today"] is False


def test_a_session_running_past_midnight_counts_for_the_new_day(client: LoggedInClient):
    from zeeguu.core.model.user_browsing_session import UserBrowsingSession

    code = _never_practiced(client)
    user = User.find(client.email)
    started_yesterday = UserBrowsingSession._create_new_session(
        db.session,
        user.id,
        current_time=server_now() - datetime.timedelta(days=1),
        language_id=user.learned_language_id,
    )

    started_yesterday_id = started_yesterday.id

    # Each session is under the minimum on its own, so only the day's sum,
    # which must include the session started yesterday, can credit today.
    client.post("/browsing_session_update", data=dict(id=started_yesterday_id, duration=100_000))
    _browse(client, 30)

    assert _streaks_by_code(client)[code]["practiced_today"] is True


def test_a_few_seconds_in_another_language_do_not_add_it(client: LoggedInClient):
    from zeeguu.core.model import Language
    from zeeguu.core.model.user_browsing_session import UserBrowsingSession

    user = User.find(client.email)
    other = Language.find_or_create("es" if user.learned_language.code != "es" else "fr")
    user_id, other_id = user.id, other.id
    session_id = UserBrowsingSession._create_new_session(db.session, user_id, language_id=other_id).id

    client.post("/browsing_session_update", data=dict(id=session_id, duration=5_000))

    assert UserLanguage.query.filter_by(user_id=user_id, language_id=other_id).first() is None


def test_the_default_goal_is_five_minutes(client: LoggedInClient):
    user = User.find(client.email)
    ul = UserLanguage.find_or_create(db.session, user, user.learned_language)
    ul.last_practiced = None
    db.session.commit()
    code = user.learned_language.code

    assert client.get("/user_preferences")["daily_goal_minutes"] == "5"
    assert _streaks_by_code(client)[code]["ms_to_streak"] == 300_000


def test_the_streak_counts_against_the_learners_goal(client: LoggedInClient):
    code = _never_practiced(client, goal_minutes=10)

    assert client.get("/user_preferences")["daily_goal_minutes"] == "10"
    _browse(client, 500)
    entry = _streaks_by_code(client)[code]
    assert entry["practiced_today"] is False
    assert entry["ms_to_streak"] == 100_000

    _browse(client, 100)
    assert _streaks_by_code(client)[code]["practiced_today"] is True


def test_a_goal_outside_the_choices_is_refused(client: LoggedInClient):
    _never_practiced(client, goal_minutes=10)

    response = client.response_from_post("/save_user_preferences", data={"daily_goal_minutes": "7"})

    assert response.status_code == 400
    assert client.get("/user_preferences")["daily_goal_minutes"] == "10"
