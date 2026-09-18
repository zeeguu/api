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
    LoggedInClient(client, email="teacher@zeeguu.test", password="test")

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
        client.post("/send_code/victim@zeeguu.test").status_code for _ in range(10)
    ]
    assert 200 in codes, "expected send_code to answer OK regardless of the address"
    assert 429 in codes, "send_code accepted 10 rapid requests without throttling"


def test_one_inbox_cannot_be_flooded_from_many_addresses(client, limiting_enabled):
    """
    The point of keying send_code on the target: an attacker who rotates IPs
    still can't put a sixth message this hour into an inbox that has had five.
    Rotation is why a per-IP number alone can't stop an email bomb.
    """
    for _ in range(10):
        client.post("/send_code/flooded@zeeguu.test")

    # A different source would get a fresh per-IP bucket; the target's is spent.
    assert client.post("/send_code/flooded@zeeguu.test").status_code == 429


def test_one_inbox_being_spent_does_not_block_everyone_else(client, limiting_enabled):
    """The target bucket must be the target's, not a global reset-code quota."""
    for _ in range(10):
        client.post("/send_code/first@zeeguu.test")

    assert client.post("/send_code/second@zeeguu.test").status_code != 429


# --- the limiter can tell one caller from another ------------------------
#
# Everything above keys on the caller's address, which is only meaningful if
# the API can see it. In production nothing reaches Flask directly: nginx
# forwards every request, so REMOTE_ADDR is the proxy and is identical for the
# whole world. Production access logs showed exactly two source addresses,
# 172.18.0.1 and 127.0.0.1, across two days of traffic.
#
# Under that, every per-IP limit is one global bucket. It cannot isolate an
# attacker, and worse: a single host making enough failed logins spends the
# budget for everybody, so the rate limit becomes a remote off-switch for
# logging in to Zeeguu. nginx now sends X-Forwarded-For and ProxyFix reads it.


def test_the_app_trusts_exactly_one_proxy(app):
    """Without ProxyFix the addresses everything above keys on are all the same."""
    from werkzeug.middleware.proxy_fix import ProxyFix

    assert isinstance(app.wsgi_app, ProxyFix)


def test_one_host_exhausting_the_limit_does_not_lock_out_everyone(client, limiting_enabled):
    """
    The failure this guards is the expensive one. If the limiter cannot tell
    callers apart, an attacker guessing passwords doesn't just get themselves
    throttled -- they throttle every legitimate user at the same time.
    """
    attacker = {"X-Forwarded-For": "203.0.113.7"}
    for i in range(400):
        client.post(
            f"/session/victim{i}@zeeguu.test", data={"password": "wrong"}, headers=attacker
        )

    # A different person, at a different address, going about their day. Note
    # the bystander needs a different account as well as a different address:
    # the per-account limit is meant to lock the account under attack, so
    # reusing one of those addresses above would be measuring the wrong thing.
    bystander = client.post(
        "/session/bystander@zeeguu.test",
        data={"password": "wrong"},
        headers={"X-Forwarded-For": "198.51.100.4"},
    ).status_code

    assert bystander != 429, "one host spending the login budget locked out everyone else"


def test_the_attacker_themselves_is_still_capped(client, limiting_enabled):
    """The other half: telling callers apart must not stop the limit applying."""
    attacker = {"X-Forwarded-For": "203.0.113.9"}
    codes = [
        client.post(
            f"/session/spray{i}@zeeguu.test", data={"password": "wrong"}, headers=attacker
        ).status_code
        for i in range(400)
    ]

    assert 429 in codes, "one address sprayed 400 accounts without being capped"


# --- a class of thirty must never meet any of this ------------------------
#
# Thirty students share one school NAT, so every per-IP limit sees them as a
# single caller. And once a bucket is spent flask-limiter turns away every
# request on that key, not just the ones that spent it -- so an IP limit a
# class can reach doesn't inconvenience the strugglers, it locks the room out,
# including the students typing the right password. The per-account limits are
# what let the IP ceilings stay above anything a real class does.

CLASS_SIZE = 30
SCHOOL_NAT = {"X-Forwarded-For": "198.51.100.30"}


def test_a_class_resetting_passwords_together_is_not_throttled(client, limiting_enabled):
    """A teacher says "everyone who forgot their password, click now"."""
    codes = [
        client.post(
            f"/send_code/student{i}@school.test", headers=SCHOOL_NAT
        ).status_code
        for i in range(CLASS_SIZE)
    ]

    assert 429 not in codes, "a class of 30 requesting reset codes hit the limit"


def test_a_class_typing_codes_in_wrongly_is_not_throttled(client, limiting_enabled):
    """The same class then enters those codes, and some get them wrong."""
    codes = [
        client.post(
            f"/reset_password/student{i}@school.test",
            data={"code": "000000", "password": "newpassword"},
            headers=SCHOOL_NAT,
        ).status_code
        for i in range(CLASS_SIZE)
    ]

    assert 429 not in codes, "a class of 30 submitting reset codes hit the limit"


def test_a_class_mistyping_passwords_is_not_throttled(client, limiting_enabled):
    """First lesson of term: thirty students, three wrong passwords each."""
    codes = [
        client.post(
            f"/session/student{i}@school.test",
            data={"password": "wrong"},
            headers=SCHOOL_NAT,
        ).status_code
        for i in range(CLASS_SIZE)
        for _ in range(3)
    ]

    assert 429 not in codes, "a class of 30 mistyping passwords locked itself out"


def test_a_class_signing_up_together_is_not_throttled(client, limiting_enabled):
    """A whole class onboarding in one lesson, on one address."""
    codes = [
        client.post(
            f"/add_user/newstudent{i}@school.test",
            data={"password": "somepassword", "username": f"Student {i}",
                  "invite_code": "", "learned_language": "de",
                  "native_language": "nl", "learned_cefr_level": "1"},
            headers=SCHOOL_NAT,
        ).status_code
        for i in range(CLASS_SIZE)
    ]

    assert 429 not in codes, "a class of 30 signing up hit the limit"


# --- but one account is still defended ------------------------------------


def test_guessing_one_account_is_capped_however_many_addresses_are_used(
    client, limiting_enabled
):
    """
    The point of the per-account key. An attacker rotating IPs defeats any
    per-IP number, so the limit that stops them has to count against the
    account being guessed at.
    """
    codes = [
        client.post(
            "/session/victim@zeeguu.test",
            data={"password": f"guess{i}"},
            headers={"X-Forwarded-For": f"203.0.113.{i}"},
        ).status_code
        for i in range(20)
    ]

    assert 429 in codes, "20 guesses at one account from 20 addresses went uncapped"
