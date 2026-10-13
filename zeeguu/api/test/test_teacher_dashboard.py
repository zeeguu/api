from datetime import datetime

from fixtures import create_and_get_article
from fixtures import logged_in_teacher as client


def test_is_teacher(client):
    result = client.get(f"/is_teacher")
    assert result == b"True"


def test_add_cohort(client):
    result = client.post("/create_own_cohort", data=FRENCH_B1_COHORT)
    assert result.decode("utf-8") == "OK"


def test_cohort_invite_code_already_in_use(client):
    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)

    response = client.response_from_post("/create_own_cohort", data=FRENCH_B1_COHORT)
    assert response.status_code == 400


def test_add_student(client):
    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)

    STUDENT_DATA["invite_code"] = FRENCH_B1_COHORT["inv_code"]
    client.post(f'/add_user/{STUDENT_DATA["email"]}', data=STUDENT_DATA)

    users = client.get("/users_from_cohort/1/14")
    print(users)
    assert users is not []
    assert users[0]["email"] == STUDENT_DATA["email"]


def test_get_class_info(client):
    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)
    cohorts = client.get("/cohorts_info")
    assert cohorts[0]["name"] == FRENCH_B1_COHORT["name"]


def test_supporter_sees_all_cohorts(client):
    from zeeguu.core.model import Cohort, Language, User
    from zeeguu.core.model.db import db

    # a class some other teacher owns
    other = Cohort("other123", "OtherClass", Language.find("fr"), 10)
    db.session.add(other)
    db.session.commit()
    other_id = other.id

    assert [c["name"] for c in client.get("/cohorts_info")] == []
    assert client.client.get(client.append_session(f"/cohort_info/{other_id}")).status_code == 401

    # being a dev is not enough: that only marks the account as the team's own
    User.find(client.email).is_dev = True
    db.session.commit()
    assert [c["name"] for c in client.get("/cohorts_info")] == []

    User.find(client.email).can_see_all_classes = True
    db.session.commit()

    assert [c["name"] for c in client.get("/cohorts_info")] == ["OtherClass"]
    assert client.get(f"/cohort_info/{other_id}")["name"] == "OtherClass"


def test_remove_cohort(client):
    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)

    resp = client.response_from_post("/remove_cohort/1")
    assert resp.status_code == 200

    resp = client.response_from_post("/remove_cohort/1")
    assert resp.status_code == 401


def test_mark_invitation_code_deleted_is_bounded_and_idempotent():
    from zeeguu.api.endpoints.teacher_dashboard.cohorts import (
        INVITATION_CODE_MAX_LENGTH,
        _mark_invitation_code_deleted,
    )

    assert _mark_invitation_code_deleted("ABC123") == "deleted_ABC123"

    # an already marked code must be left alone: stacking the marker is what
    # overflowed the column and made remove_cohort 500 before deleting anything
    assert _mark_invitation_code_deleted("deleted_ABC123") == "deleted_ABC123"

    assert _mark_invitation_code_deleted(None) is None

    # when it does not fit, the code is what gets clipped -- never the marker
    marked = _mark_invitation_code_deleted("x" * INVITATION_CODE_MAX_LENGTH)
    assert len(marked) == INVITATION_CODE_MAX_LENGTH
    assert marked.startswith("deleted_")


def test_update_cohort(client):
    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)

    update_info = {
        "inv_code": "123",
        "name": "SpanishB1",
        "max_students": "11",
        "language_code": "de",
    }

    client.post("/update_cohort/1", data=update_info)

    cohorts = client.get("/cohorts_info")
    assert cohorts is not []


def test_cohorts_info_reports_last_shared_time(client):
    from zeeguu.core.model import Article, Cohort, CohortArticleMap
    from zeeguu.core.model.db import db

    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)
    client.post("/create_own_cohort", data=SECOND_COHORT)

    article = create_and_get_article(client)
    db.session.add(
        CohortArticleMap(
            Cohort.find_by_code(FRENCH_B1_COHORT["inv_code"]),
            Article.find_by_id(article["id"]),
            datetime.now(),
        )
    )
    db.session.commit()

    cohorts_by_name = {c["name"]: c for c in client.get("/cohorts_info")}

    # the client orders a teacher's classes by this; None means "never used"
    assert cohorts_by_name[FRENCH_B1_COHORT["name"]]["last_shared_time"] is not None
    assert cohorts_by_name[SECOND_COHORT["name"]]["last_shared_time"] is None


def test_student_does_not_have_access_to_cohort(client):
    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)
    cohorts = client.get("/cohorts_info")

    # Create a student user and log them in
    student_data = dict(password="test", username="test", learned_language="fr")
    email = "student@mir.lu"
    response = client.response_from_post(f"/add_user/{email}", data=student_data)
    student_session = response.data.decode("utf-8")

    # Ensure student user can't access /cohorts_info
    # 403 Forbidden: authenticated but not authorized (not a teacher)
    response = client.client.get(f"/cohorts_info?session={student_session}")
    assert response.status_code == 403


def test_teacher_decides_whether_students_see_each_other(client):
    cohort = dict(FRENCH_B1_COHORT, students_see_each_other="false")
    client.post("/create_own_cohort", data=cohort)
    assert client.get("/cohort_info/1")["students_see_each_other"] is False

    student_data = dict(
        password="test", username="peer", learned_language="fr", invite_code="123"
    )
    response = client.response_from_post("/add_user/peer@mir.lu", data=student_data)
    student_session = response.data.decode("utf-8")
    leaderboard = "/cohort_leaderboard/1?metric=reading_time"

    def student_status():
        url = f"{leaderboard}&session={student_session}"
        return client.client.get(url).status_code

    assert student_status() == 403
    # the teacher still sees the whole class
    assert client.client.get(client.append_session(leaderboard)).status_code == 200

    # an update without the field leaves the choice as it was
    update_info = dict(inv_code="123", name="FrenchB1", language_code="fr")
    client.post("/update_cohort/1", data=update_info)
    assert student_status() == 403

    client.post("/update_cohort/1", data=dict(update_info, students_see_each_other="true"))
    assert student_status() == 200


def test_teacher_cannot_read_students_of_another_class(client):
    from zeeguu.core.model import Cohort, Language, User
    from zeeguu.core.model.db import db

    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)
    other = Cohort("other123", "OtherClass", Language.find("fr"), 10)
    db.session.add(other)
    db.session.commit()
    other_id = other.id

    def join(email, invite_code):
        data = dict(password="test", username=email, learned_language="fr")
        client.response_from_post(f"/add_user/{email}", data=dict(data, invite_code=invite_code))
        return User.find(email).id

    own_student = join("own@mir.lu", FRENCH_B1_COHORT["inv_code"])
    foreign_student = join("foreign@mir.lu", "other123")

    def status(student_id, cohort_id):
        params = dict(student_id=student_id, cohort_id=cohort_id, number_of_days=14)
        return client.response_from_post("/student_activity_overview", data=params).status_code

    assert status(own_student, 1) == 200
    assert status(foreign_student, other_id) == 401

    client.get(f"/remove_user_from_cohort/{foreign_student}/{other_id}")
    assert User.find_by_id(foreign_student).is_member_of_cohort(other_id)


def test_cohorts_info_reports_last_activity(client):
    from zeeguu.core.model import Language, User
    from zeeguu.core.model.db import db
    from zeeguu.core.model.user_language import UserLanguage

    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)
    client.post("/create_own_cohort", data=SECOND_COHORT)

    def member(email, invite_code):
        data = dict(password="test", username=email, learned_language="fr", invite_code=invite_code)
        client.response_from_post(f"/add_user/{email}", data=data)
        return User.find(email)

    def practised_french(user, when):
        ul = UserLanguage.find_or_create(db.session, user, Language.find("fr"))
        ul.last_practiced = when
        db.session.commit()  # before the next request ends the session

    practised_french(member("student@mir.lu", "123"), datetime(2026, 10, 1, 12, 0))
    # later, but doesn't count: a developer practising, a member merely seen
    dev = member("dev@mir.lu", "123")
    dev.is_dev = True
    practised_french(dev, datetime(2026, 10, 5, 12, 0))
    seen = member("seen@mir.lu", "456")
    seen.last_seen = datetime(2026, 10, 9, 12, 0)
    db.session.commit()

    cohorts_by_name = {c["name"]: c for c in client.get("/cohorts_info")}

    # the client sorts classes by this: a student practising, or a text shared
    assert cohorts_by_name[FRENCH_B1_COHORT["name"]]["last_activity"].startswith("2026-10-01")
    assert cohorts_by_name[SECOND_COHORT["name"]]["last_activity"] is None


FRENCH_B1_COHORT = {
    "inv_code": "123",
    "name": "FrenchB1",
    "language_id": "fr",
    "max_students": 33,
}

SECOND_COHORT = {
    "inv_code": "456",
    "name": "FrenchA2",
    "language_id": "fr",
    "max_students": 33,
}

WRONG_INVITE_CODE_COHORT = {
    "inv_code": "123",
    "name": "FrenchB2",
    "language_id": "fr",
    "max_students": "33",
}

STUDENT_DATA = {
    "username": "student1",
    "password": "password",
    "email": "student1@gmail.com",
}
