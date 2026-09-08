"""
Rate limits are configuration that looks correct whether or not it works, so
these tests check that it is actually wired up rather than merely declared.

Every key in RATE_LIMITS used to be prefixed "api." while the blueprint is
named "endpoints", so every lookup returned None and the failure was swallowed
by a bare except. Login accepted unlimited attempts for as long as that stood.

The second group of tests is about the opposite failure: limits that do fire,
on people who did nothing wrong. A class shares one school NAT, so an IP bucket
is a whole room in one quota.
"""

import pytest

from zeeguu.api.test.fixtures import client, LoggedInClient
from zeeguu.api.utils.rate_limiter import RATE_LIMITS, get_limiter


@pytest.fixture
def limiting_enabled():
    """The suite runs with the limiter off; switch it on for one test."""
    limiter = get_limiter()
    limiter.enabled = True
    yield limiter
    limiter.enabled = False
    limiter.reset()


def _login(client, email, password):
    return client.post(f"/session/{email}", data={"password": password}).status_code


# --- the limits exist and fire -------------------------------------------


def test_every_configured_endpoint_exists(app):
    """A limit on an endpoint name that doesn't resolve protects nothing."""
    unknown = sorted(ep for ep in RATE_LIMITS if ep not in app.view_functions)
    assert unknown == [], f"rate limits point at non-existent endpoints: {unknown}"


def test_repeated_login_failures_are_capped(client, limiting_enabled):
    """100 failures per minute, so a run of 105 wrong passwords must be cut off."""
    codes = [_login(client, "nobody@zeeguu.test", "wrong") for _ in range(105)]
    assert 429 in codes, "login accepted 105 rapid failures without throttling"


def test_user_search_is_capped(client, limiting_enabled):
    """
    Search takes a full email address as a key, so an unbounded endpoint would
    let a script sweep a wordlist to learn which addresses have an account.
    """
    codes = [
        client.get("/search_users?query=probe&session=a-session-uuid").status_code
        for _ in range(70)
    ]
    assert 429 in codes, "user search accepted 70 rapid queries without throttling"


# --- and don't fire on legitimate crowds ---------------------------------


def test_a_room_of_sixty_can_all_log_in(client, limiting_enabled, _mock_web):
    """
    The demo case, and every classroom: 60 people behind one school NAT, all
    signing in within a couple of minutes. Not one of them may see a 429.
    """
    account = LoggedInClient(client, email="teacher@zeeguu.test", password="test")

    codes = [_login(client, "teacher@zeeguu.test", "test") for _ in range(60)]
    assert 429 not in codes, "a room of 60 legitimate logins hit the rate limit"


def test_successful_logins_are_not_charged_to_the_failure_budget(
    client, limiting_enabled, _mock_web
):
    """
    Correct sign-ins are free, which is what lets the failure ceiling be low
    enough to matter without a busy classroom ever approaching it.
    """
    LoggedInClient(client, email="busy@zeeguu.test", password="test")

    for _ in range(150):
        _login(client, "busy@zeeguu.test", "test")

    assert _login(client, "busy@zeeguu.test", "test") != 429


def test_search_buckets_are_per_session_not_per_ip(client, limiting_enabled):
    """
    A classroom shares one NAT address. Exhausting one student's quota must not
    lock out the student sitting next to them.
    """
    for _ in range(70):
        client.get("/search_users?query=probe&session=first-student")

    second = client.get("/search_users?query=probe&session=second-student")
    assert second.status_code != 429, "one session's quota spilled onto another's"


def test_reset_code_requests_are_capped_even_though_they_all_succeed(
    client, limiting_enabled
):
    """
    send_code answers "OK" for unknown addresses too, so that it can't be used
    to enumerate users. Charging it on failures would therefore never charge
    anything, and looping it would be an unlimited email bomb aimed at whoever
    the address belongs to.
    """
    codes = [
        client.post("/send_code/victim@zeeguu.test").status_code for _ in range(25)
    ]
    assert 200 in codes, "expected send_code to answer OK regardless of the address"
    assert 429 in codes, "send_code accepted 25 rapid requests without throttling"
