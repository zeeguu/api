from zeeguu.api.test.fixtures import client

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
