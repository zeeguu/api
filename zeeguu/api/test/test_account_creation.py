from zeeguu.api.test.fixtures import client
from zeeguu.core.model import db, UniqueCode
import json

TEST_PASS = "test"
TEST_EMAIL = "i@mir.lu"
TEST_USER = "test_user"


def test_add_user(client):
    test_user_data = dict(password=TEST_PASS, username=TEST_USER)

    response = client.post(f"/add_user/{TEST_EMAIL}", data=test_user_data)
    assert int(response.data)


def test_cant_add_same_email_twice(client):
    test_user_data = dict(password=TEST_PASS, username=TEST_USER)
    response = client.post(f"/add_user/{TEST_EMAIL}", data=test_user_data)
    assert int(response.data)

    response = client.post(f"/add_user/{TEST_EMAIL}", data=test_user_data)
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "There is already an account for this email" in data["message"]


def test_create_user_returns_400_if_password_too_short(client):
    form_data = dict(username="gigi", password="2sh", invite_code="test")
    response = client.post("/add_user/i@i.la", data=form_data)
    assert response.status_code == 400


def test_create_user_returns_400_if_password_absent(client):
    form_data = dict(username="gigi", invite_code="test")
    response = client.post("/add_user/i@i.la", data=form_data)
    assert response.status_code == 400


def test_create_user_returns_400_if_password_not_given(client):
    form_data = dict(username="gigi")
    response = client.post("/add_user/i@i.la", data=form_data)
    assert response.status_code == 400


def test_reset_password(client):
    _create_test_user(client)

    code = UniqueCode(TEST_EMAIL)
    db.session.add(code)
    db.session.commit()

    form_data = dict(code=code, password="updated")
    rv = client.post("/reset_password/" + TEST_EMAIL, data=form_data)
    assert rv.status_code == 200


def test_reset_password_can_use_new_password(client):
    _create_test_user(client)

    code = UniqueCode(TEST_EMAIL)
    db.session.add(code)
    db.session.commit()

    form_data = dict(code=code, password="updated")
    rv = client.post("/reset_password/" + TEST_EMAIL, data=form_data)
    assert rv.status_code == 200

    form_data = dict(password="updated")

    rv = client.post("/session/" + TEST_EMAIL, data=form_data)

    assert rv.status_code == 200


def test_reset_password_returns_400_invalid_code(client):
    _create_test_user(client)

    code = UniqueCode(TEST_EMAIL)
    db.session.add(code)
    db.session.commit()

    # invalid_code
    form_data = dict(code="thiswontwork", password="updated")
    rv = client.post("/reset_password/" + TEST_EMAIL, data=form_data)
    assert rv.status_code == 400

    # password too short
    form_data = dict(code=code, password="2sh")
    rv = client.post("/reset_password/" + TEST_EMAIL, data=form_data)
    assert rv.status_code == 400


def _create_test_user(client):
    test_user_data = dict(password=TEST_PASS, username=TEST_USER)

    _ = client.post(f"/add_user/{TEST_EMAIL}", data=test_user_data)
