import json
import pytest

from zeeguu.api.test.fixtures import client, LoggedInClient
from zeeguu.core.model import User
from zeeguu.core.model.db import db

TEST_PASS = "test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def logged_in(client, email, password=TEST_PASS):
    """Create a user via /add_user and return a LoggedInClient."""
    return LoggedInClient(client, email=email, password=password)


def set_username(lc, username):
    """Set the username of a logged-in user via /user_settings."""
    return lc.response_from_post("/user_settings", data={"username": username})


# NOTE: Currently /add_user always auto-generates the username field; the 'username'
# form parameter goes to the display *name*, not the username column.
# All username-specific validation and changes go through /user_settings.


# ===========================================================================
# Save Validation (special characters)
# ===========================================================================

class TestUsernameValidation:

    # --- Whitespace handling -----------------------------------------------

    def test_username_leading_trailing_whitespace_is_stripped(self, app, client):
        lc = logged_in(client, "strip@zeeguu.test")
        response = set_username(lc, "  braveuser  ")
        assert response.status_code == 200
        user = User.find("strip@zeeguu.test")
        assert user.username == "braveuser"

    def test_username_exactly_max_length_accepted(self, app, client):
        lc = logged_in(client, "exact50@zeeguu.test")
        response = set_username(lc, "a" * 50)
        assert response.status_code == 200

    def test_username_too_long_rejected(self, app, client):
        lc = logged_in(client, "long51@zeeguu.test")
        response = set_username(lc, "a" * 51)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "50" in data["message"]

    def test_username_whitespace_only_rejected(self, app, client):
        """Whitespace-only username strips to empty string → ValueError → 400."""
        lc = logged_in(client, "whitespace@zeeguu.test")
        response = set_username(lc, "   ")
        assert response.status_code == 400

    def test_username_empty_silently_ignored(self, app, client):
        """
        Empty string is falsy — the /user_settings endpoint skips it entirely.
        The username remains unchanged and 200 is returned.
        This documents the current behaviour; the username is NOT updated.
        """
        lc = logged_in(client, "emptyupdate@zeeguu.test")
        original_user = User.find("emptyupdate@zeeguu.test")
        original_username = original_user.username

        response = set_username(lc, "")
        assert response.status_code == 200
        user = User.find("emptyupdate@zeeguu.test")
        assert user.username == original_username

    # --- Special characters ------------------------------------------------

    def test_username_with_accented_chars(self, app, client):
        lc = logged_in(client, "accented@zeeguu.test")
        response = set_username(lc, "ëlïté42")
        assert response.status_code == 200
        user = User.find("accented@zeeguu.test")
        assert user.username == "ëlïté42"

    def test_username_with_symbols(self, app, client):
        """No character whitelist — symbols are currently accepted."""
        lc = logged_in(client, "symbols@zeeguu.test")
        response = set_username(lc, "user@name!")
        assert response.status_code == 200

    def test_username_with_underscore_and_hyphen(self, app, client):
        lc = logged_in(client, "hyphenscore@zeeguu.test")
        response = set_username(lc, "cool-user_99")
        assert response.status_code == 200

    def test_username_with_emoji(self, app, client):
        """Document behaviour: emoji is 1 char in Python but 4 bytes in utf8mb4."""
        lc = logged_in(client, "emoji@zeeguu.test")
        response = set_username(lc, "🦁lion42")
        # No assertion on outcome — documents actual behaviour.
        assert response.status_code in (200, 400)

    def test_username_numbers_only(self, app, client):
        lc = logged_in(client, "numbers@zeeguu.test")
        response = set_username(lc, "12345")
        assert response.status_code == 200

    def test_username_unicode(self, app, client):
        """Document behaviour: Chinese characters in utf8mb4 column."""
        lc = logged_in(client, "unicode@zeeguu.test")
        response = set_username(lc, "用户名42")
        assert response.status_code in (200, 400)

    def test_username_with_internal_spaces(self, app, client):
        """Internal spaces are accepted — only leading/trailing whitespace is stripped."""
        lc = logged_in(client, "internal@zeeguu.test")
        response = set_username(lc, "brave wolf")
        assert response.status_code == 200
        user = User.find("internal@zeeguu.test")
        assert user.username == "brave wolf"

    # --- Case sensitivity --------------------------------------------------

    def test_username_update_own_case_change(self, app, client):
        """A user should be able to change only the casing of their own username."""
        lc = logged_in(client, "owncase@zeeguu.test")
        set_username(lc, "myuser99")

        response = set_username(lc, "MYUSER99")
        assert response.status_code == 200

        user = User.find("owncase@zeeguu.test")
        assert user.username.upper() == "MYUSER99"

    # --- Update via /user_settings -----------------------------------------
    def test_update_username_success(self, app, client):
        lc = logged_in(client, "update1@zeeguu.test")
        response = set_username(lc, "newname42")
        assert response.status_code == 200

        user = User.find("update1@zeeguu.test")
        assert user.username == "newname42"

    def test_update_username_duplicate_rejected(self, app, client):
        lc1 = logged_in(client, "taken@zeeguu.test")
        set_username(lc1, "takenname1")

        lc2 = logged_in(client, "updater@zeeguu.test")
        response = set_username(lc2, "takenname1")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Username already in use" in data["message"]


# ===========================================================================
# Phase 2: Search
# ===========================================================================

class TestUsernameSearch:

    def test_search_users_partial_match(self, app, client):
        lc_target = logged_in(client, "searchable@zeeguu.test")
        set_username(lc_target, "brave_tiger1")

        lc = logged_in(client, "searcher@zeeguu.test")
        results = lc.get("/search_users?query=brave")
        usernames = [r["username"] for r in results]
        assert "brave_tiger1" in usernames

    def test_search_users_case_insensitive(self, app, client):
        lc_target = logged_in(client, "caseuser@zeeguu.test")
        set_username(lc_target, "brave_owl2")

        lc = logged_in(client, "casesearcher@zeeguu.test")
        results = lc.get("/search_users?query=BRAVE")
        usernames = [r["username"] for r in results]
        assert "brave_owl2" in usernames

    def test_search_users_self_excluded(self, app, client):
        lc = logged_in(client, "selfcheck@zeeguu.test")
        set_username(lc, "selfcheck_unique1")

        results = lc.get("/search_users?query=selfcheck_unique1")
        usernames = [r["username"] for r in results]
        assert "selfcheck_unique1" not in usernames

    def test_search_users_no_match(self, app, client):
        lc = logged_in(client, "nomatch@zeeguu.test")
        results = lc.get("/search_users?query=xyzzy_no_such_user_123456789")
        assert results == []

    def test_search_users_empty_term(self, app, client):
        lc = logged_in(client, "emptyq@zeeguu.test")
        results = lc.get("/search_users?query=")
        assert results == []

    def test_search_users_special_chars_in_username(self, app, client):
        lc_target = logged_in(client, "accentedsearch@zeeguu.test")
        set_username(lc_target, "ëlïté99")

        lc = logged_in(client, "accentsearcher@zeeguu.test")
        results = lc.get("/search_users?query=ëlïté")
        usernames = [r["username"] for r in results]
        assert "ëlïté99" in usernames

    def test_search_users_exact_email_match(self, app, client):
        """Email search is not supported; searching by email returns no results."""
        logged_in(client, "emailsearch@zeeguu.test")
        lc = logged_in(client, "emailsearcher@zeeguu.test")

        results = lc.get("/search_users?query=emailsearch@zeeguu.test")
        assert results == []

    def test_search_users_sql_injection_safe(self, app, client):
        lc = logged_in(client, "sqlinj@zeeguu.test")

        import urllib.parse
        payload = urllib.parse.quote("'; DROP TABLE user; --")
        results = lc.get(f"/search_users?query={payload}")
        # Should return an empty list without crashing or exposing data
        assert isinstance(results, list)
        assert results == []
