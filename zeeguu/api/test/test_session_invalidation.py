from zeeguu.api.test.fixtures import client, LoggedInClient
from zeeguu.api.utils.route_wrappers import SESSION_CACHE
from zeeguu.core.model import UniqueCode
from zeeguu.core.model.db import db

TEST_EMAIL = "i@mir.lu"
TEST_PASS = "test"


def logged_in(client):
    return LoggedInClient(client, email=TEST_EMAIL, password=TEST_PASS)


def another_session(client, password=TEST_PASS):
    response = client.post(f"/session/{TEST_EMAIL}", data=dict(password=password))
    assert response.status_code == 200
    return response.get_json()["session"]


def is_valid(client, session):
    # Drop the cookie that /session set, so only the query param is in play
    client.delete_cookie("chocolatechip")
    return client.get(f"/validate?session={session}").status_code == 200


def test_debug_master_password_does_not_log_in(app, client):
    logged_in(client)
    with app.app_context():
        from zeeguu.core.model import User

        user_id = User.find(TEST_EMAIL).id
    app.config["DEBUG_USER_ID"] = user_id
    app.config["DEBUG_USER_PASSWORD"] = "masterkey"
    try:
        response = client.post(
            f"/session/{TEST_EMAIL}", data=dict(password="masterkey")
        )
        assert response.status_code == 401
    finally:
        app.config.pop("DEBUG_USER_ID")
        app.config.pop("DEBUG_USER_PASSWORD")


def test_password_reset_ends_every_session(client):
    user = logged_in(client)
    other = another_session(client)
    # Used once, so both are in the session cache too
    assert is_valid(client, user.session)
    assert is_valid(client, other)

    code = UniqueCode(TEST_EMAIL, UniqueCode.RESET)
    db.session.add(code)
    db.session.commit()
    code_value = code.code
    response = client.post(
        f"/reset_password/{TEST_EMAIL}", data=dict(code=code_value, password="updated")
    )
    assert response.status_code == 200

    assert not is_valid(client, user.session)
    assert not is_valid(client, other)
    assert is_valid(client, another_session(client, password="updated"))


def test_password_change_keeps_only_the_current_session(client):
    user = logged_in(client)
    other = another_session(client)
    assert is_valid(client, other)

    client.delete_cookie("chocolatechip")
    response = user.response_from_post("/user_settings", data=dict(password="updated"))
    assert response.status_code == 200

    assert is_valid(client, user.session)
    assert not is_valid(client, other)


def test_logged_out_session_is_rejected_even_when_cached(client):
    user = logged_in(client)
    assert is_valid(client, user.session)
    assert user.session in SESSION_CACHE

    assert client.get(f"/logout_session?session={user.session}").status_code == 200

    assert user.session not in SESSION_CACHE
    assert not is_valid(client, user.session)


def test_logout_with_the_session_cookie_only(client):
    logged_in(client)
    session = another_session(client)  # also sets the cookie

    response = client.get("/logout_session")
    assert response.status_code == 200
    assert client.get_cookie("chocolatechip") is None

    assert not is_valid(client, session)


def test_session_cookie_is_secure_outside_debug(app, client):
    logged_in(client)
    response = client.post(f"/session/{TEST_EMAIL}", data=dict(password=TEST_PASS))
    assert "Secure" in response.headers["Set-Cookie"]

    app.config["DEBUG"] = True
    try:
        response = client.post(
            f"/session/{TEST_EMAIL}", data=dict(password=TEST_PASS)
        )
        assert "Secure" not in response.headers["Set-Cookie"]
    finally:
        app.config["DEBUG"] = False
