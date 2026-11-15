"""Accounts whose password the web sent unencoded at signup can still log in.

Before the web encoded the form body, `password=a+b&c` reached the API as
"a b": the rest was cut at the &, + became a space. That is what such
accounts have stored, while the web now sends what the user actually typed.
"""
from zeeguu.api.test.fixtures import client, LoggedInClient

EMAIL = "i@mir.lu"


def _login(client, password):
    return client.post(f"/session/{EMAIL}", data=dict(password=password))


def test_password_stored_mangled_by_the_old_signup_still_logs_in(client):
    LoggedInClient(client, email=EMAIL, password="secret 1")  # typed "secret+1&x"

    assert _login(client, "secret+1&x").status_code == 200


def test_password_stored_correctly_logs_in_as_typed(client):
    LoggedInClient(client, email=EMAIL, password="secret+1&x")

    assert _login(client, "secret+1&x").status_code == 200


def test_old_form_does_not_let_a_prefix_in(client):
    LoggedInClient(client, email=EMAIL, password="secret+1&x")

    assert _login(client, "secret 1").status_code == 401
    assert _login(client, "secret+1&y").status_code == 401
