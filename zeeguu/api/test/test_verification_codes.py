"""
Codes mailed to an address, and the endpoints that redeem them.

Three properties, each tested on its own and then together:
  - a code only works for what it was issued for (reset vs. verification);
  - the answer to a failed redemption is the same however it failed, and
    /complete_account_upgrade refuses an address with an account before it
    looks at any code;
  - a code stops working after UniqueCode.MAX_ATTEMPTS submissions, which is
    stored in the row, so it holds across workers and restarts.
"""

import json
from datetime import datetime, timedelta

from zeeguu.api.test.fixtures import client
from zeeguu.core.model import UniqueCode, User
from zeeguu.core.model.db import db

VICTIM = "owner@zeeguu.test"
VICTIM_PASS = "owner-password"


def _create_user(client, email=VICTIM, password=VICTIM_PASS):
    rv = client.post(f"/add_user/{email}", data=dict(password=password, username="Owner"))
    assert rv.status_code == 200
    return rv.data.decode("utf-8")


def _anon_session(client, uuid="anon-visitor"):
    rv = client.post("/add_anon_user", data=dict(uuid=uuid, password="anonpass"))
    assert rv.status_code == 200
    return rv.data.decode("utf-8")


def _latest(email, purpose):
    code_obj = UniqueCode.find_last_code(email, purpose)
    return code_obj.code if code_obj else None


def _wrong(code):
    return str((int(code) + 1) % 10000).zfill(4)


def _issue(email, purpose):
    code_obj = UniqueCode(email, purpose)
    db.session.add(code_obj)
    db.session.commit()
    return code_obj.code


def _upgrade(client, session, email, code):
    return client.post(
        f"/complete_account_upgrade?session={session}",
        data=dict(email=email, code=code, password="newpass"),
    )


def _reset(client, email, code, password="taken-over"):
    return client.post(f"/reset_password/{email}", data=dict(code=code, password=password))


def _confirm(client, session, code):
    return client.post(f"/confirm_email?session={session}", data=dict(code=code))


def _can_log_in(client, email, password):
    return client.post(f"/session/{email}", data=dict(password=password)).status_code == 200


# --- purposes are kept apart ------------------------------------------------


def test_send_code_issues_a_reset_code(client):
    _create_user(client)
    client.post(f"/send_code/{VICTIM}")

    assert _latest(VICTIM, UniqueCode.RESET) is not None


def test_a_reset_code_does_not_confirm_an_email(client):
    session = _create_user(client, email="unconfirmed@zeeguu.test")
    # Signup issued a verification code; drop it so only the reset code exists.
    for c in UniqueCode.all_codes_for("unconfirmed@zeeguu.test"):
        db.session.delete(c)
    db.session.commit()
    reset_code = _issue("unconfirmed@zeeguu.test", UniqueCode.RESET)

    assert _confirm(client, session, reset_code).status_code == 400
    assert not User.find("unconfirmed@zeeguu.test").email_verified


def test_a_reset_code_does_not_upgrade_an_account(client):
    session = _anon_session(client)
    reset_code = _issue("fresh@zeeguu.test", UniqueCode.RESET)

    assert _upgrade(client, session, "fresh@zeeguu.test", reset_code).status_code == 400
    assert not User.email_exists("fresh@zeeguu.test")


def test_a_verification_code_does_not_reset_a_password(client):
    _create_user(client)
    verify_code = _issue(VICTIM, UniqueCode.VERIFY)

    assert _reset(client, VICTIM, verify_code).status_code == 400
    assert _can_log_in(client, VICTIM, VICTIM_PASS)


def test_codes_of_the_right_purpose_still_work(client):
    """The separation must not cost the legitimate flows anything."""
    _create_user(client)
    client.post(f"/send_code/{VICTIM}")
    assert _reset(client, VICTIM, _latest(VICTIM, UniqueCode.RESET), "brand-new").status_code == 200
    assert _can_log_in(client, VICTIM, "brand-new")

    session = _anon_session(client)
    client.post(f"/request_email_verification?session={session}", data=dict(email="new@zeeguu.test"))
    code = _latest("new@zeeguu.test", UniqueCode.VERIFY)
    assert _upgrade(client, session, "new@zeeguu.test", code).status_code == 200
    assert User.find("new@zeeguu.test").email_verified


def test_confirm_email_with_the_right_code(client):
    session = _create_user(client, email="confirm@zeeguu.test")
    code = _latest("confirm@zeeguu.test", UniqueCode.VERIFY)

    assert _confirm(client, session, code).status_code == 200
    assert User.find("confirm@zeeguu.test").email_verified


def test_send_code_mails_the_address_on_the_account(client, monkeypatch):
    """
    The code is stored under, and mailed to, the account's own address, even
    when the route spells it differently (the email column's collation makes
    more spellings match than lower() does).
    """
    sent_to = []
    monkeypatch.setattr(
        "zeeguu.core.emailer.password_reset.send_password_reset_email",
        lambda to_email, code: sent_to.append(to_email),
    )
    _create_user(client)
    monkeypatch.setattr(User, "find", classmethod(lambda cls, email: cls.query.filter_by(email=VICTIM).one()))

    client.post("/send_code/OWNER@zeeguu.test")

    assert sent_to == [VICTIM]
    assert _latest(VICTIM, UniqueCode.RESET) is not None


# --- one answer for every failure -------------------------------------------


def test_upgrade_to_an_address_with_an_account_is_refused_before_the_code(client):
    _create_user(client)
    client.post(f"/send_code/{VICTIM}")
    real = _latest(VICTIM, UniqueCode.RESET)
    session = _anon_session(client)

    right = _upgrade(client, session, VICTIM, real)
    wrong = _upgrade(client, session, VICTIM, _wrong(real))

    assert right.status_code == wrong.status_code == 400
    assert right.data == wrong.data
    # And the code was never even consulted, so it was not used up either.
    assert UniqueCode.find_last_code(VICTIM, UniqueCode.RESET).attempts == 0


def test_upgrade_failures_all_look_the_same(client):
    session = _anon_session(client)
    _create_user(client)

    no_code = _upgrade(client, session, "nocode@zeeguu.test", "1234")

    code = _issue("wrongcode@zeeguu.test", UniqueCode.VERIFY)
    wrong_code = _upgrade(client, session, "wrongcode@zeeguu.test", _wrong(code))

    expired = UniqueCode("expired@zeeguu.test", UniqueCode.VERIFY)
    expired.time = datetime.now() - timedelta(hours=1)
    db.session.add(expired)
    db.session.commit()
    expired_code = _upgrade(client, session, "expired@zeeguu.test", expired.code)

    taken = _upgrade(client, session, VICTIM, "1234")

    answers = {(r.status_code, json.loads(r.data)["message"]) for r in (no_code, wrong_code, expired_code, taken)}
    assert len(answers) == 1
    status, message = answers.pop()
    assert status == 400
    # The web upgrade flow keys "go back and request a new code" on this word.
    assert "expired" in message


def test_upgrade_matches_the_address_case_insensitively(client):
    _create_user(client)
    session = _anon_session(client, uuid="visitor")

    rv = _upgrade(client, session, "OWNER@zeeguu.test", "1234")

    assert rv.status_code == 400
    assert User.find("visitor@anon.zeeguu").is_anonymous()


# --- codes wear out ------------------------------------------------------------


def test_a_code_stops_working_after_max_attempts(client):
    _create_user(client)
    client.post(f"/send_code/{VICTIM}")
    real = _latest(VICTIM, UniqueCode.RESET)

    for _ in range(UniqueCode.MAX_ATTEMPTS):
        assert _reset(client, VICTIM, _wrong(real)).status_code == 400

    assert _reset(client, VICTIM, real).status_code == 400
    assert _can_log_in(client, VICTIM, VICTIM_PASS)


def test_a_new_code_starts_with_fresh_attempts(client):
    _create_user(client)
    client.post(f"/send_code/{VICTIM}")
    first = _latest(VICTIM, UniqueCode.RESET)
    for _ in range(UniqueCode.MAX_ATTEMPTS):
        _reset(client, VICTIM, _wrong(first))

    db.session.query(UniqueCode).update({UniqueCode.time: datetime.now() - timedelta(minutes=1)})
    db.session.commit()
    client.post(f"/send_code/{VICTIM}")

    assert _reset(client, VICTIM, _latest(VICTIM, UniqueCode.RESET), "brand-new").status_code == 200


def test_confirm_email_codes_wear_out_too(client):
    session = _create_user(client, email="confirm@zeeguu.test")
    real = _latest("confirm@zeeguu.test", UniqueCode.VERIFY)

    for _ in range(UniqueCode.MAX_ATTEMPTS):
        _confirm(client, session, _wrong(real))

    assert _confirm(client, session, real).status_code == 400
    assert not User.find("confirm@zeeguu.test").email_verified


def test_upgrade_codes_wear_out_too(client):
    session = _anon_session(client)
    real = _issue("fresh@zeeguu.test", UniqueCode.VERIFY)

    for _ in range(UniqueCode.MAX_ATTEMPTS):
        _upgrade(client, session, "fresh@zeeguu.test", _wrong(real))

    assert _upgrade(client, session, "fresh@zeeguu.test", real).status_code == 400
    assert not User.email_exists("fresh@zeeguu.test")


# --- the whole sequence ---------------------------------------------------------


def test_reset_code_cannot_be_learned_through_the_upgrade_endpoint(client):
    """
    End to end: an anonymous session asks for a reset code for someone else's
    address, then tries codes against /complete_account_upgrade. The answers
    must not tell the right code from a wrong one, and guessing at
    /reset_password directly must run out long before the code space does.
    """
    _create_user(client)
    session = _anon_session(client, uuid="visitor")

    assert client.post(f"/send_code/{VICTIM}").status_code == 200
    real = _latest(VICTIM, UniqueCode.RESET)

    # Every candidate, the right one included, gets the identical answer.
    candidates = [str(i).zfill(4) for i in range(50)] + [real]
    answers = {
        (r.status_code, r.data)
        for r in (_upgrade(client, session, VICTIM, c) for c in candidates)
    }
    assert len(answers) == 1
    assert answers.pop()[0] == 400

    # Guessing at the reset endpoint: the code is used up after MAX_ATTEMPTS,
    # and then even the right value is refused.
    guesses = [c for c in (str(i).zfill(4) for i in range(10000)) if c != real]
    for guess in guesses[: UniqueCode.MAX_ATTEMPTS]:
        assert _reset(client, VICTIM, guess).status_code == 400
    assert _reset(client, VICTIM, real).status_code == 400

    # The account is untouched and the visitor is still anonymous.
    assert _can_log_in(client, VICTIM, VICTIM_PASS)
    assert not _can_log_in(client, VICTIM, "taken-over")
    assert User.find("visitor@anon.zeeguu").is_anonymous()
