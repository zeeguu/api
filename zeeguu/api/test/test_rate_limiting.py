"""
Rate limits are configuration that looks correct whether or not it works, so
these tests check that it is actually wired up rather than merely declared.

Every key in RATE_LIMITS used to be prefixed "api." while the blueprint is
named "endpoints", so every lookup returned None and the failure was swallowed
by a bare except. Login accepted unlimited attempts for as long as that stood.
"""

import pytest

from zeeguu.api.test.fixtures import client
from zeeguu.api.utils.rate_limiter import (
    RATE_LIMITS,
    PER_SESSION_RATE_LIMITS,
    get_limiter,
)


@pytest.fixture
def limiting_enabled():
    """The suite runs with the limiter off; switch it on for one test."""
    limiter = get_limiter()
    limiter.enabled = True
    yield limiter
    limiter.enabled = False
    limiter.reset()


def test_every_configured_endpoint_exists(app):
    """A limit on an endpoint name that doesn't resolve protects nothing."""
    configured = {**RATE_LIMITS, **PER_SESSION_RATE_LIMITS}
    unknown = sorted(ep for ep in configured if ep not in app.view_functions)
    assert unknown == [], f"rate limits point at non-existent endpoints: {unknown}"


def test_login_attempts_are_actually_capped(client, limiting_enabled):
    """5 per minute, so the 15th rapid attempt must not still be answered."""
    codes = [
        client.post("/session/nobody@zeeguu.test", data={"password": "wrong"}).status_code
        for _ in range(15)
    ]
    assert 429 in codes, f"login accepted 15 rapid attempts without throttling: {codes}"


def test_user_search_is_capped_per_session(client, limiting_enabled):
    """
    Search takes a full email address as a key, so an unbounded endpoint would
    let a script sweep a wordlist to learn which addresses have an account.
    """
    codes = [
        client.get("/search_users?query=probe&session=a-session-uuid").status_code
        for _ in range(70)
    ]
    assert 429 in codes, "user search accepted 70 rapid queries without throttling"


def test_search_buckets_are_per_session_not_per_ip(client, limiting_enabled):
    """
    A classroom shares one NAT address. Exhausting one student's quota must not
    lock out the student sitting next to them.
    """
    for _ in range(70):
        client.get("/search_users?query=probe&session=first-student")

    second = client.get("/search_users?query=probe&session=second-student")
    assert second.status_code != 429, "one session's quota spilled onto another's"
