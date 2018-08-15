import json
from unittest import TestCase

from tests_zeeguu_api.api_test_mixin import APITestMixin

import zeeguu


class _UserInfo():
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
            username=self.username,
            password=self.password,
            invite_code=self.invite_code
        )


test_teacher = _UserInfo('testUser', 'password', 'test', 'test321@gmail.com')
test_teacher2 = _UserInfo('testUser2', 'password2', 'test', 'teacher2@gmail.com')

test_student_1 = {
    'username': 'student1',
    'password': 'password',
    'email': 'student1@gmail.com'
}

test_student_2 = {
    'username': 'student2',
    'password': 'password',
    'email': 'student2@gmail.com'
}

test_student_3 = {
    'username': 'student3',
    'password': 'password',
    'email': 'student3@gmail.com'
}


french_b1 = {'inv_code': '123',
             'name': 'FrenchB1',
             'language_id': 'fr',
             'max_students': 33
             }

french_b2 = {'inv_code': '1235',
             'name': 'FrenchB2',
             'language_id': 'fr',
             'max_students': '33'
             }

french_b2_wrong_invcode = {'inv_code': '123',
                           'name': 'FrenchB2',
                           'language_id': 'fr',
                           'max_students': '33'
                           }

french_b2_wrong_students = {'inv_code': '1234',
                            'name': 'FrenchB2',
                            'language_id': 'fr',
                            'max_students': '-33'
                            }

french_b2_wrong_language = {'inv_code': '1234',
                            'name': 'FrenchB2',
                            'language_id': 'frr',
                            'max_students': '33'
                            }


class DashboardTest(APITestMixin, TestCase):

    def setUp(self):
        super(DashboardTest, self).setUp()
        zeeguu.app.config["INVITATION_CODES"] = ["test"]

    def test_is_teacher(self):
        session = self._create_teacher(test_teacher)
        result = self.app.post(f'/create_own_cohort?session={session}', data=french_b1)

        assert result.status_code == 200
        assert result.data.decode("utf-8") == "OK"

        answer = self.app.get(f'/is_teacher?session={session}')
        assert answer.data == b'True'

    def test_adding_classes(self):
        session = self._create_teacher(test_teacher)

        result = self.app.post(f'/create_own_cohort?session={session}', data=french_b1)
        assert result.status_code == 200

        assert result.data.decode("utf-8") == "OK"

        # Inv code already in use
        result = self.app.post(f'/create_own_cohort?session={session}', data=french_b2_wrong_invcode)
        assert result.status_code == 400

        # invalid max_students
        result = self.app.post(f'/create_own_cohort?session={session}', data=french_b2_wrong_students)
        assert result.status_code == 400

        # invalid language_id
        result = self.app.post(f'/create_own_cohort?session={session}', data=french_b2_wrong_language)
        assert result.status_code == 400

    def test_get_classes_and_get_class_info(self):
        # Insert class from another teacher

        t1_session = self._create_teacher(test_teacher)
        result = self.app.post(f'/create_own_cohort?session={t1_session}', data=french_b1)
        assert result.status_code == 200

        # Insert class from teacher we will test
        t2_session = self._create_teacher(test_teacher2)
        result = self.app.post(f'/create_own_cohort?session={t2_session}', data=french_b2)
        assert result.status_code == 200

        classes_json_data = self.app.get(f'/cohorts_info?session={t2_session}')
        classes = json.loads(classes_json_data.data)
        teacher2s_class = classes[0]
        assert teacher2s_class['name'] == 'FrenchB2'

        # Test get class info
        result = self.app.get(f'cohort_info/{teacher2s_class["id"]}?session={t2_session}')
        assert result.status_code == 200
        assert json.loads(result.data)['name'] == 'FrenchB2'

        # Test get class info for class the teacher doesn't have access too
        result = self.app.get(f'cohort_info/1?session={t2_session}')
        assert result.status_code == 401

        # Test get class info for class that doesn't exist
        result = self.app.get(f'cohort_info/5?session={t2_session}')
        assert result.status_code == 401

    def _create_teacher_and_class(self, teacher, cohort):
        teacher_session = self._create_teacher(teacher)
        result = self.app.post(f'/create_own_cohort?session={teacher_session}', data=cohort)
        return teacher_session, result

    def test_add_student_to_class_success(self):
        self._create_teacher_and_class(test_teacher, french_b1)

        result = self._add_student(test_student_1, french_b1['inv_code'])
        assert result.status_code == 200

    def test_add_student_to_class_wrong_invite_code(self):
        self._create_teacher_and_class(test_teacher, french_b1)

        result = self._add_student(test_student_2, "wild_guess")
        assert result.status_code == 400

    def test_get_users_from_class(self):

        teacher_session, _ = self._create_teacher_and_class(test_teacher, french_b1)
        self._add_student(test_student_1, french_b1['inv_code'])
        self._add_student(test_student_2, french_b1['inv_code'])

        # Get list of users in a class
        result = self.app.get(f'/users_from_cohort/1/14?session={teacher_session}')
        assert result.status_code == 200

        student_1 = json.loads(result.data)[0]

        assert student_1['name'] == test_student_1['username']

        # Get individual user
        result = self.app.get(f'/user_info/{student_1["id"]}/14?session={teacher_session}')
        assert result.status_code == 200
        result = json.loads(result.data)
        assert result['name'] == 'student1'

        # User that doesn't exists
        result = self.app.get(f'/user_info/55/14?session={teacher_session}')
        assert result.status_code == 400

        # User not in class owned by teacher
        self._add_student(test_student_3, 'test')

        result = self.app.get(f'/user_info/5/14?session={teacher_session}')
        assert result.status_code == 401

    def test_remove_class(self):

        teacher_session,_ = self._create_teacher_and_class(test_teacher, french_b1)

        # Remove class that teacher owns
        result = self.app.post(f'/remove_cohort/1?session={teacher_session}')
        assert result.status_code == 200

        # Try to remove class that is already removed
        result = self.app.post(f'/remove_cohort/1?session={teacher_session}')
        assert result.status_code == 401

    def test_update_class(self):
        teacher_session, _ = self._create_teacher_and_class(test_teacher, french_b1)

        # Test valid update
        updateDictionary = {
            'inv_code': '123',
            'name': 'SpanishB1',
            'max_students': '11'
        }
        result = self.app.post(f'/update_cohort/1?session={teacher_session}', data=updateDictionary)
        assert result.status_code == 200

        result = self.app.get(f'/cohort_info/1?session={teacher_session}')
        assert result.status_code == 200

        loaded = json.loads(result.data)
        assert loaded['name'] == 'SpanishB1'
        assert loaded['max_students'] == 11
        assert loaded['inv_code'] == '123'

    def test_invalid_update_class(self):
        # Test invalid update (negative max students)

        teacher_session, _ = self._create_teacher_and_class(test_teacher, french_b1)

        update_info = {
            'inv_code': '123',
            'name': 'SpanishB1',
            'max_students': '-11'
        }
        result = self.app.post(f'/update_cohort/1?session={teacher_session}', data=update_info)
        assert result.status_code == 400

        result = self.app.get(f'/cohort_info/1?session={teacher_session}')
        loaded = json.loads(result.data)

        assert loaded['max_students'] == french_b1['max_students']

    def test_more_invalid_updates(self):
        # Test invalid update (negative max students)

        teacher_session, _ = self._create_teacher_and_class(test_teacher, french_b1)
        teacher2_session, _ = self._create_teacher_and_class(test_teacher2, french_b2)

        # Test invalid update (taken inv code)
        update_dictionary = {
            'inv_code': french_b2['inv_code'],
            'name': 'SpanishB1',
            'max_students': '11'
        }
        result = self.app.post(f'/update_cohort/1?session={teacher_session}', data=update_dictionary)
        assert result.status_code == 400

        # Test invalid permissions
        update_dictionary = {
            'inv_code': '1245',
            'name': 'SpanishB1',
            'max_students': '11'
        }
        result = self.app.post(f'/update_cohort/2?session={teacher_session}', data=update_dictionary)
        assert result.status_code == 401

    def _create_teacher(self, teacher: _UserInfo):
        def _upgrade_to_teacher(email):
            from zeeguu.model import User, Teacher
            db = zeeguu.db

            u = User.find(email)
            db.session.add(Teacher(u))
            db.session.commit()

        rv = self.api_post(f'/add_user/{teacher.email}', teacher.data_dict())

        session = rv.data.decode('utf-8')

        _upgrade_to_teacher(teacher.email)
        return session

    def _add_student(self, student, inv_code):
        student['invite_code'] = inv_code
        return self.app.post(f'/add_user/{student["email"]}', data=student)


