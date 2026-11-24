from zeeguu.api.test.fixtures import client, LoggedInClient
from zeeguu.core.constants import PLATFORM_ANDROID_APP, PLATFORM_IOS_APP, PLATFORM_UNKNOWN
from zeeguu.core.model import Session

EMAIL = "i@mir.lu"
PASSWORD = "test"


def _platform_of(session_uuid):
    return Session.find(session_uuid).platform


def test_login_records_the_platform(client):
    LoggedInClient(client, email=EMAIL, password=PASSWORD)

    response = client.post(
        f"/session/{EMAIL}", data=dict(password=PASSWORD, platform=PLATFORM_ANDROID_APP)
    )

    assert _platform_of(response.get_json()["session"]) == PLATFORM_ANDROID_APP


def test_anon_signup_records_the_platform(client):
    response = client.post(
        "/add_anon_user",
        data=dict(uuid="anon-platform", password="pw", platform=PLATFORM_IOS_APP),
    )

    assert response.status_code == 200
    assert _platform_of(response.data.decode("utf-8")) == PLATFORM_IOS_APP


def test_login_without_a_valid_platform_leaves_it_empty(client):
    LoggedInClient(client, email=EMAIL, password=PASSWORD)

    old_client = client.post(f"/session/{EMAIL}", data=dict(password=PASSWORD))
    junk = client.post(f"/session/{EMAIL}", data=dict(password=PASSWORD, platform="ios"))

    assert _platform_of(old_client.get_json()["session"]) is None
    assert _platform_of(junk.get_json()["session"]) is None


# Sessions from before logins stored their platform get it from the first
# request that reports one (remember_session_platform).


def test_an_old_session_gets_its_platform_from_a_later_request(client):
    learner = LoggedInClient(client, email=EMAIL, password=PASSWORD)
    assert _platform_of(learner.session) is None

    learner.post("/browsing_session_start", data=dict(platform=PLATFORM_IOS_APP))

    assert _platform_of(learner.session) == PLATFORM_IOS_APP


def test_activity_uploads_also_fill_in_the_platform(client):
    learner = LoggedInClient(client, email=EMAIL, password=PASSWORD)

    learner.post(
        "/upload_user_activity_data",
        data=dict(
            time="2026-11-24T10:00:00.000Z",
            event="TEST EVENT",
            value="",
            extra_data="{}",
            platform=PLATFORM_ANDROID_APP,
        ),
    )

    assert _platform_of(learner.session) == PLATFORM_ANDROID_APP


def test_a_stored_platform_is_never_overwritten(client):
    learner = LoggedInClient(client, email=EMAIL, password=PASSWORD)
    learner.post("/exercise_session_start", data=dict(platform=PLATFORM_IOS_APP))

    learner.post("/exercise_session_start", data=dict(platform=PLATFORM_ANDROID_APP))

    assert _platform_of(learner.session) == PLATFORM_IOS_APP


def test_unknown_or_junk_platforms_are_not_stored(client):
    learner = LoggedInClient(client, email=EMAIL, password=PASSWORD)

    learner.post("/browsing_session_start", data=dict(platform=PLATFORM_UNKNOWN))
    learner.response_from_post("/upload_user_activity_data", data=dict(
        time="2026-11-24T10:00:00.000Z", event="TEST EVENT", value="", extra_data="{}", platform="ios"))

    assert _platform_of(learner.session) is None
