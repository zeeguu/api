"""
/join_cohort follows the same capacity rule as signing up with a class code:
a full class, or one closed with max_students=-10 (how event codes are shut),
takes nobody new.
"""

import json

from zeeguu.api.test.fixtures import client, LoggedInClient
from zeeguu.core.model import Cohort, Language, User
from zeeguu.core.model.db import db


def _cohort(code, max_students):
    cohort = Cohort(code, f"Class {code}", Language.find("de"), max_students)
    db.session.add(cohort)
    db.session.commit()
    return cohort.id


def _join(student, code):
    return student.response_from_post("/join_cohort", data=dict(invite_code=code))


def _is_member(email, cohort_id):
    return User.find(email).is_member_of_cohort(cohort_id)


def test_joining_an_open_class(client, _mock_web):
    student = LoggedInClient(client, email="student@zeeguu.test")
    cohort_id = _cohort("open-class", 30)

    rv = _join(student, "open-class")

    assert rv.status_code == 200 and rv.data == b"OK"
    assert _is_member("student@zeeguu.test", cohort_id)


def test_a_closed_class_cannot_be_joined(client, _mock_web):
    student = LoggedInClient(client, email="student@zeeguu.test")
    cohort_id = _cohort("closed-event", -10)

    rv = _join(student, "closed-event")

    assert rv.status_code == 400
    assert "No more places" in json.loads(rv.data)["message"]
    assert not _is_member("student@zeeguu.test", cohort_id)


def test_a_full_class_cannot_be_joined(client, _mock_web):
    # Room for max_students + 10, i.e. exactly one student here.
    first = LoggedInClient(client, email="first@zeeguu.test")
    second = LoggedInClient(client, email="second@zeeguu.test")
    cohort_id = _cohort("tiny-class", -9)

    assert _join(first, "tiny-class").status_code == 200
    assert _join(second, "tiny-class").status_code == 400
    assert not _is_member("second@zeeguu.test", cohort_id)


def test_a_class_without_max_students_can_still_be_joined(client, _mock_web):
    student = LoggedInClient(client, email="student@zeeguu.test")
    cohort_id = _cohort("no-limit", None)

    assert _join(student, "no-limit").status_code == 200
    assert _is_member("student@zeeguu.test", cohort_id)


def test_an_unknown_code_is_a_client_error(client, _mock_web):
    student = LoggedInClient(client, email="student@zeeguu.test")

    assert _join(student, "no-such-class").status_code == 400
