from zeeguu.api.test.fixtures import logged_in_client
from zeeguu.core.model import User

TEST_PASS = "test"


class TestUserSettingsDoesNotChangeThePassword:
    """
    A session is not proof of the password. If /user_settings took a new one,
    whoever holds a session (a stolen cookie) could lock the owner out, and then
    pass every check that asks for the password again. Changing the password goes
    through /send_code + /reset_password, which prove control of the mailbox.
    """

    def test_a_new_password_is_refused(self, app, logged_in_client):
        response = logged_in_client.response_from_post(
            "/user_settings", data=dict(password="stolen-session-pass")
        )

        assert response.status_code == 400
        assert "reset-password" in response.get_data(as_text=True)

    def test_the_old_password_still_logs_in(self, app, logged_in_client):
        logged_in_client.response_from_post(
            "/user_settings", data=dict(password="stolen-session-pass")
        )

        with app.app_context():
            assert User.authorize(logged_in_client.email, TEST_PASS) is not None
            assert User.authorize(logged_in_client.email, "stolen-session-pass") is None

    def test_nothing_else_in_the_request_is_written(self, app, logged_in_client):
        # The refusal happens before any write, so a name riding along with the
        # password must not stick either.
        with app.app_context():
            name_before = User.find(logged_in_client.email).name

        logged_in_client.response_from_post(
            "/user_settings",
            data=dict(name="Should Not Stick", password="stolen-session-pass"),
        )

        with app.app_context():
            assert User.find(logged_in_client.email).name == name_before

    def test_an_empty_password_field_is_ignored(self, app, logged_in_client):
        # Mirrors the old gate: an empty field never meant "change the password",
        # so a client posting one alongside a real change must still get a save.
        response = logged_in_client.response_from_post(
            "/user_settings", data=dict(name="Renamed", password="")
        )

        assert response.status_code == 200
        with app.app_context():
            assert User.find(logged_in_client.email).name == "Renamed"
            assert User.authorize(logged_in_client.email, TEST_PASS) is not None
