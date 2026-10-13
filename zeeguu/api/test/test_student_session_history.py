from datetime import datetime, timedelta

from fixtures import logged_in_teacher as client
from zeeguu.core.model import Cohort, Language, User, UserBrowsingSession
from zeeguu.core.model.db import db

FRENCH_CLASS = {"inv_code": "fr123", "name": "French", "language_id": "fr", "max_students": 10}


def _join(client, email, invite_code, learned_language="fr"):
    data = dict(
        password="test",
        username=email,
        learned_language=learned_language,
        invite_code=invite_code,
    )
    response = client.client.post(f"/add_user/{email}", data=data)
    return User.find(email), response.data.decode("utf-8")


def _browse(user, language_code, days_ago):
    session = UserBrowsingSession(
        user.id,
        datetime.now() - timedelta(days=days_ago),
        language_id=Language.find(language_code).id,
    )
    session.duration = 60 * 1000
    db.session.add(session)
    db.session.commit()


def _history_url(student, cohort_id, days=60):
    return f"/student_session_history?student_id={student.id}&cohort_id={cohort_id}&days={days}"


def test_teacher_sees_student_history_in_the_class_language(client):
    client.post("/create_own_cohort", data=FRENCH_CLASS)
    student, _ = _join(client, "student@mir.lu", "fr123")
    _browse(student, "fr", days_ago=40)
    _browse(student, "de", days_ago=2)

    sessions = client.get(_history_url(student, 1))

    assert [s["session_type"] for s in sessions] == ["browsing"]


def test_teacher_of_another_class_cannot_see_history(client):
    other = Cohort("other123", "Other", Language.find("fr"), 10)
    db.session.add(other)
    db.session.commit()
    other_id = other.id
    stranger, _ = _join(client, "stranger@mir.lu", "other123")

    url = client.append_session(_history_url(stranger, other_id))
    assert client.client.get(url).status_code == 401


def test_classmate_cannot_see_history(client):
    client.post("/create_own_cohort", data=FRENCH_CLASS)
    student, _ = _join(client, "student@mir.lu", "fr123")
    _, classmate_session = _join(client, "classmate@mir.lu", "fr123")

    url = _history_url(student, 1) + f"&session={classmate_session}"
    assert client.client.get(url).status_code == 401


def test_learner_history_goes_back_beyond_thirty_days(client):
    student, student_session = _join(client, "learner@mir.lu", None)
    _browse(student, "fr", days_ago=45)

    url = f"/session_history?days=60&session={student_session}"
    sessions = client.client.get(url).get_json()

    assert len(sessions) == 1
