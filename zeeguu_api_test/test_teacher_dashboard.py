import json
from unittest import TestCase

from zeeguu_api_test.api_test_mixin import APITestMixin

import zeeguu_core


class _UserInfo:
    """
    for keeping user info together
    """

    def __init__(self, username, password, invite_code, email):
        self.username = username
        self.password = password
        self.invite_code = invite_code
        self.email = email

    def data_dict(self):
        return dict(
            username=self.username, password=self.password, invite_code=self.invite_code
        )


test_teacher = _UserInfo("testUser", "password", "test", "test321@gmail.com")
test_teacher2 = _UserInfo("testUser2", "password2", "test", "teacher2@gmail.com")

test_student_1 = {
    "username": "student1",
    "password": "password",
    "email": "student1@gmail.com",
}

test_student_2 = {
    "username": "student2",
    "password": "password",
    "email": "student2@gmail.com",
}

test_student_3 = {
    "username": "student3",
    "password": "password",
    "email": "student3@gmail.com",
}

french_b1 = {
    "inv_code": "123",
    "name": "FrenchB1",
    "language_id": "fr",
    "max_students": 33,
}

french_b2 = {
    "inv_code": "1235",
    "name": "FrenchB2",
    "language_id": "fr",
    "max_students": "33",
}

french_b2_wrong_invcode = {
    "inv_code": "123",
    "name": "FrenchB2",
    "language_id": "fr",
    "max_students": "33",
}

french_b2_wrong_students = {
    "inv_code": "1234",
    "name": "FrenchB2",
    "language_id": "fr",
    "max_students": "-33",
}

french_b2_wrong_language = {
    "inv_code": "1234",
    "name": "FrenchB2",
    "language_id": "frr",
    "max_students": "33",
}


class TeacherTest(APITestMixin, TestCase):
    def setUp(self):
        super(TeacherTest, self).setUp()
        zeeguu_core.app.config["INVITATION_CODES"] = ["test"]

    def test_is_teacher(self):
        session = self._create_teacher(test_teacher)
        answer = self.app.get(f"/is_teacher?session={session}")
        assert answer.data == b"True"

    def test_adding_classes(self):
        session, result = self._create_teacher_and_class(test_teacher, french_b1)
        assert result.status_code == 200

        # Inv code already in use
        result = self.app.post(
            f"/create_own_cohort?session={session}", data=french_b2_wrong_invcode
        )
        assert result.status_code == 400

        # invalid max_students
        result = self.app.post(
            f"/create_own_cohort?session={session}", data=french_b2_wrong_students
        )
        assert result.status_code == 400

        # invalid language_id
        result = self.app.post(
            f"/create_own_cohort?session={session}", data=french_b2_wrong_language
        )
        assert result.status_code == 400

    def test_get_classes_and_get_class_info(self):
        # Insert class from another teacher
        t1_session, result = self._create_teacher_and_class(test_teacher, french_b1)
        assert result.status_code == 200

        # Insert class from teacher we will test
        t2_session, result = self._create_teacher_and_class(test_teacher2, french_b2)
        assert result.status_code == 200

        # cohorts info should contain only frenchb2 for our teacher2
        classes_json = self.app.get(f"/cohorts_info?session={t2_session}")
        class_of_teacher2 = json.loads(classes_json.data)[0]
        class_of_teacher2_name = class_of_teacher2["name"]
        assert class_of_teacher2_name == "FrenchB2"

        # Test get class info
        class_of_teacher2_id = class_of_teacher2["id"]
        result = self.app.get(
            f"cohort_info/{class_of_teacher2_id}?session={t2_session}"
        )
        assert result.status_code == 200
        assert json.loads(result.data)["name"] == "FrenchB2"

        # Test get class info for class the teacher doesn't have access to
        result = self.app.get(f"cohort_info/1?session={t2_session}")
        assert result.status_code == 401

        # Test get class info for class that doesn't exist
        result = self.app.get(f"cohort_info/5?session={t2_session}")
        assert result.status_code == 401

    def test_add_student_to_class_success(self):
        self._create_teacher_and_class(test_teacher, french_b1)

        result = self._add_student(test_student_1, french_b1["inv_code"])
        assert result.status_code == 200

    def test_add_student_to_class_wrong_invite_code(self):
        self._create_teacher_and_class(test_teacher, french_b1)

        result = self._add_student(test_student_2, "wild_guess")
        assert result.status_code == 400

    def test_get_users_from_class(self):
        teacher_session, _ = self._create_teacher_and_class(test_teacher, french_b1)
        self._add_student(test_student_1, french_b1["inv_code"])
        self._add_student(test_student_2, french_b1["inv_code"])

        # Get list of users in a class
        result = self.app.get(f"/users_from_cohort/1/14?session={teacher_session}")
        assert result.status_code == 200

        student_1 = json.loads(result.data)[0]

        assert student_1["name"] == test_student_1["username"]

        # Get individual user
        result = self.app.get(
            f'/user_info/{student_1["id"]}/14?session={teacher_session}'
        )
        assert result.status_code == 200
        result = json.loads(result.data)
        assert result["name"] == "student1"

        # User that doesn't exists
        result = self.app.get(f"/user_info/55/14?session={teacher_session}")
        assert result.status_code == 400

        # User not in class owned by teacher
        self._add_student(test_student_3, "test")

        result = self.app.get(f"/user_info/5/14?session={teacher_session}")
        assert result.status_code == 401

    def test_remove_class(self):
        teacher_session, _ = self._create_teacher_and_class(test_teacher, french_b1)

        # Remove class that teacher owns
        result = self.app.post(f"/remove_cohort/1?session={teacher_session}")
        assert result.status_code == 200

        # Try to remove class that is already removed
        result = self.app.post(f"/remove_cohort/1?session={teacher_session}")
        assert result.status_code == 401

    def test_update_class(self):
        teacher_session, _ = self._create_teacher_and_class(test_teacher, french_b1)

        # Test valid update
        update_info = {
            "inv_code": "123",
            "name": "SpanishB1",
            "max_students": "11",
            "language_code": "de",
        }
        result = self.app.post(
            f"/update_cohort/1?session={teacher_session}", data=update_info
        )
        assert result.status_code == 200

        result = self.app.get(f"/cohort_info/1?session={teacher_session}")
        assert result.status_code == 200

        loaded = json.loads(result.data)
        assert loaded["name"] == "SpanishB1"
        assert loaded["max_students"] >= 11
        assert loaded["inv_code"] == "123"

    def test_more_invalid_updates(self):
        # Test invalid update (negative max students)

        teacher_session, _ = self._create_teacher_and_class(test_teacher, french_b1)
        teacher2_session, _ = self._create_teacher_and_class(test_teacher2, french_b2)

        # Test invalid update (taken inv code)
        update_info = {
            "inv_code": french_b2["inv_code"],
            "name": "SpanishB1",
            "max_students": "11",
        }
        result = self.app.post(
            f"/update_cohort/1?session={teacher_session}", data=update_info
        )
        assert result.status_code == 400

        # Test invalid permissions
        update_info = {"inv_code": "1245", "name": "SpanishB1", "max_students": "11"}
        result = self.app.post(
            f"/update_cohort/2?session={teacher_session}", data=update_info
        )
        assert result.status_code == 401

    # Private, helper methods

    def _create_teacher(self, teacher: _UserInfo):
        def _upgrade_to_teacher(email):
            from zeeguu_core.model import User, Teacher

            db = zeeguu_core.db

            u = User.find(email)
            db.session.add(Teacher(u))
            db.session.commit()

        rv = self.api_post(f"/add_user/{teacher.email}", teacher.data_dict())

        session = rv.data.decode("utf-8")

        _upgrade_to_teacher(teacher.email)
        return session

    def _add_student(self, student, inv_code):
        student["invite_code"] = inv_code
        return self.app.post(f'/add_user/{student["email"]}', data=student)

    def _create_teacher_and_class(self, teacher, cohort):
        teacher_session = self._create_teacher(teacher)
        result = self.app.post(
            f"/create_own_cohort?session={teacher_session}", data=cohort
        )
        return teacher_session, result
