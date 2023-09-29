from fixtures import logged_in_teacher as client


def test_is_teacher(client):
    result = client.get(f"/is_teacher")
    assert result == b"True"


def test_add_cohort(client):
    result = client.post("/create_own_cohort", data=FRENCH_B1_COHORT)
    assert result.decode('utf-8') == 'OK'


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


def test_remove_cohort(client):
    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)

    resp = client.response_from_post("/remove_cohort/1")
    assert resp.status_code == 200

    resp = client.response_from_post("/remove_cohort/1")
    assert resp.status_code == 401


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


def test_student_does_not_have_access_to_cohort(client):
    client.post("/create_own_cohort", data=FRENCH_B1_COHORT)
    cohorts = client.get("/cohorts_info")

    # Create a student user and log them in
    student_data = dict(
        password="test", username="test", learned_language="fr"
    )
    email = "student@mir.lu"
    response = client.response_from_post(f"/add_user/{email}", data=student_data)
    student_session = int(response.data)

    # Ensure student user can't access /cohorts_info
    response = client.client.get(f"/cohorts_info?session={student_session}")
    assert response.status_code == 401


FRENCH_B1_COHORT = {
    "inv_code": "123",
    "name": "FrenchB1",
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
