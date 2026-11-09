"""
A guest ("start without an account") who signs up with a class's invite code
joins that class, like a student who signs up with an email does. With a code
that names no class, or a full one, the guest still gets an account, just
without a class.
"""

from zeeguu.api.test.fixtures import client
from zeeguu.core.model import Cohort, Language, UniqueCode, User
from zeeguu.core.model.db import db


def _cohort(client, code, max_students, teachers=False):
    with client.application.app_context():
        cohort = Cohort(code, f"Class {code}", Language.find("de"), max_students)
        cohort.is_cohort_of_teachers = teachers
        db.session.add(cohort)
        db.session.commit()
        return cohort.id


def _guest_signup(client, uuid, invite_code):
    rv = client.post(
        "/add_anon_user",
        data=dict(uuid=uuid, password="anonpass", learned_language_code="de", invite_code=invite_code),
    )
    assert rv.status_code == 200
    return rv.data.decode("utf-8")


def _classes_of_guest(client, uuid):
    with client.application.app_context():
        guest = User.find(uuid + User.ANONYMOUS_EMAIL_DOMAIN)
        assert guest is not None
        return {membership.cohort_id for membership in guest.cohorts}


def test_guest_with_a_class_code_joins_the_class(client, _mock_web):
    cohort_id = _cohort(client, "challenge-class", 30)

    _guest_signup(client, "guest-1", "Challenge-Class")

    assert _classes_of_guest(client, "guest-1") == {cohort_id}


def test_guest_with_an_unknown_code_gets_an_account_without_a_class(client, _mock_web):
    _guest_signup(client, "guest-2", "no-such-class")

    assert _classes_of_guest(client, "guest-2") == set()


def test_guest_is_not_added_to_a_full_class(client, _mock_web):
    # max_students=-10 is how event codes are closed: room for nobody.
    _cohort(client, "closed-event", -10)

    _guest_signup(client, "guest-3", "closed-event")

    assert _classes_of_guest(client, "guest-3") == set()


def test_guest_does_not_join_a_class_of_teachers(client, _mock_web):
    _cohort(client, "teachers-only", 30, teachers=True)

    _guest_signup(client, "guest-4", "teachers-only")

    assert _classes_of_guest(client, "guest-4") == set()


def test_a_guest_in_a_class_can_still_upgrade_to_a_full_account(client, _mock_web):
    # The upgrade also joins the class of the invite code; for a guest who is
    # already in it, that must not insert a second user_cohort_map row.
    cohort_id = _cohort(client, "upgrade-class", 30)
    session = _guest_signup(client, "guest-5", "upgrade-class")
    with client.application.app_context():
        code = UniqueCode("upgraded@zeeguu.test", UniqueCode.VERIFY)
        db.session.add(code)
        db.session.commit()
        code = code.code

    rv = client.post(
        f"/complete_account_upgrade?session={session}",
        data=dict(email="upgraded@zeeguu.test", code=code, password="newpass"),
    )

    assert rv.status_code == 200
    with client.application.app_context():
        upgraded = User.find("upgraded@zeeguu.test")
        assert {membership.cohort_id for membership in upgraded.cohorts} == {cohort_id}
