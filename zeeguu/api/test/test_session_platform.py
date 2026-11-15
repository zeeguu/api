from zeeguu.api.test.fixtures import client, LoggedInClient
from zeeguu.core.constants import PLATFORM_ANDROID_APP, PLATFORM_IOS_APP
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
