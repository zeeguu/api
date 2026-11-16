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


def test_joining_a_class_twice_is_ok(client, _mock_web):
    student = LoggedInClient(client, email="student@zeeguu.test")
    cohort_id = _cohort("twice", 30)

    assert _join(student, "twice").status_code == 200
    rv = _join(student, "twice")

    assert rv.status_code == 200 and rv.data == b"OK"
    assert _is_member("student@zeeguu.test", cohort_id)


def test_a_member_of_a_full_class_can_rejoin_it(client, _mock_web):
    student = LoggedInClient(client, email="student@zeeguu.test")
    _cohort("full-once-in", -9)

    assert _join(student, "full-once-in").status_code == 200
    assert _join(student, "full-once-in").status_code == 200


def _goal(student):
    return student.get("/user_preferences")["daily_goal_minutes"]


def _cohort_with_goal(code, minutes):
    cohort_id = _cohort(code, 30)
    cohort = Cohort.query.get(cohort_id)
    cohort.daily_goal_minutes = minutes
    db.session.commit()
    return cohort_id


def test_a_class_with_a_daily_goal_sets_it_for_who_joins(client, _mock_web):
    student = LoggedInClient(client, email="student@zeeguu.test")
    _cohort_with_goal("study-class", 10)
    assert _goal(student) == "5"

    assert _join(student, "study-class").status_code == 200

    assert _goal(student) == "10"


def test_a_class_goal_never_lowers_the_learners_goal(client, _mock_web):
    student = LoggedInClient(client, email="student@zeeguu.test")
    student.post("/save_user_preferences", data={"daily_goal_minutes": "15"})
    _cohort_with_goal("study-class", 10)

    _join(student, "study-class")

    assert _goal(student) == "15"


def test_a_class_without_a_goal_leaves_the_learners_goal(client, _mock_web):
    student = LoggedInClient(client, email="student@zeeguu.test")
    _cohort("plain-class", 30)

    _join(student, "plain-class")

    assert _goal(student) == "5"


def test_signing_up_with_the_code_of_a_class_with_a_goal(client, _mock_web):
    from zeeguu.core.model import UserPreference

    with client.application.app_context():
        _cohort_with_goal("study-signup", 10)
    data = dict(password="test", username="newbie", learned_language="de", invite_code="study-signup")
    assert client.post("/add_user/newbie@zeeguu.test", data=data).status_code == 200

    with client.application.app_context():
        newbie = User.find("newbie@zeeguu.test")
        assert newbie.is_member_of_cohort(Cohort.find_by_code("study-signup").id)
        assert UserPreference.get_daily_goal_minutes(newbie) == 10
