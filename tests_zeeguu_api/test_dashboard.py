import json
from unittest import TestCase

from tests_zeeguu_api.api_test_mixin import APITestMixin

import zeeguu
from zeeguu_api.app import app


class DashboardTest(APITestMixin, TestCase):

    def test_has_session(self):
        # TEST FOR FAKE SESSION
        result = self.app.get('/has_session?session=31235ds')
        result = json.loads(result.data)
        assert result == 0

        # TEST FOR REAL SESSION
        userDictionary = {
            'username': 'testUser',
            'password': 'password'
        }
        rv = self.api_post('/add_user/test321@gmail.com', userDictionary)
        assert rv
        result = self.app.get('/has_session?session=' + rv.data.decode('utf-8'))
        result = json.loads(result.data)
        assert result == 1

    def test_adding_classes(self):
        userDictionary = {
            'username': 'testUser',
            'password': 'password'
        }
        rv = self.api_post('/add_user/test321@gmail.com', userDictionary)
        assert rv

        # Acceptable class
        classDictionary = {
            'inv_code': '123',
            'class_name': 'FrenchB1',
            'class_language_id': 'fr',
            'max_students': '33'
        }
        result = self.app.post('/add_class?session=' + rv.data.decode('utf-8'), data=classDictionary)
        assert result.status_code == 200
        result = json.loads(result.data)
        assert result == 1

        # Inv code aleady in use
        classDictionary = {
            'inv_code': '123',
            'class_name': 'FrenchB2',
            'class_language_id': 'fr',
            'max_students': '33'
        }
        result = self.app.post('/add_class?session=' + rv.data.decode('utf-8'), data=classDictionary)
        assert result.status_code == 400

        # invalid max_students
        classDictionary = {
            'inv_code': '1234',
            'class_name': 'FrenchB2',
            'class_language_id': 'fr',
            'max_students': '-15'
        }
        result = self.app.post('/add_class?session=' + rv.data.decode('utf-8'), data=classDictionary)
        assert result.status_code == 400


        # invalid language_id
        classDictionary = {
            'inv_code': '12345',
            'class_name': 'FrenchB3',
            'class_language_id': 'frrrr',
            'max_students': '10'
        }
        result = self.app.post('/add_class?session=' + rv.data.decode('utf-8'), data=classDictionary)
        assert result.status_code == 400

    def test_get_classes_and_get_class_info(self):
        # Insert class from another teacher
        userDictionary = {
            'username': 'testUser1',
            'password': 'password'
        }
        rv = self.api_post('/add_user/test3210@gmail.com', userDictionary)
        classDictionary = {
            'inv_code': '12',
            'class_name': 'FrenchB1',
            'class_language_id': 'fr',
            'max_students': '33'
        }
        result = self.app.post('/add_class?session=' + rv.data.decode('utf-8'), data=classDictionary)

        # Insert class from teacher we will test
        userDictionary = {
            'username': 'testUser2',
            'password': 'password'
        }
        rv = self.api_post('/add_user/test321@gmail.com', userDictionary)
        classDictionary = {
            'inv_code': '123',
            'class_name': 'FrenchB2',
            'class_language_id': 'fr',
            'max_students': '33'
        }
        result = self.app.post('/add_class?session=' + rv.data.decode('utf-8'), data=classDictionary)
        classesJ = self.app.get('/get_classes?session=' + rv.data.decode('utf-8'))
        assert classesJ
        classes = json.loads(classesJ.data)
        # Assert something is returned
        assert classes

        # Assert the correct class of the two is returned
        assert classes[0]['class_name'] == 'FrenchB2'

        # Test get class info
        result = self.app.get('get_class_info/' + str(classes[0]['id']) + '?session=' + rv.data.decode('utf-8'))
        assert result.status_code == 200
        assert json.loads(result.data)['class_name'] == 'FrenchB2'

        # Test get class info for class the teacher doesn't have access too
        result = self.app.get('get_class_info/1' + '?session=' + rv.data.decode('utf-8'))
        assert result.status_code ==401

        # Test get class info for class that doesn't exist
        result = self.app.get('get_class_info/5' + '?session=' + rv.data.decode('utf-8'))
        assert result.status_code == 401


    def test_get_users_from_class_and_without(self):


        userDictionary = {
            'username': 'testUser1',
            'password': 'password'
        }
        rv = self.api_post('/add_user/test3210@gmail.com', userDictionary)
        classDictionary = {
            'inv_code': '12',
            'class_name': 'FrenchB1',
            'class_language_id': 'fr',
            'max_students': '10'
        }
        result = self.app.post('/add_class?session=' + rv.data.decode('utf-8'), data=classDictionary)

        newUser = {
            'username': 'newUser1',
            'password': 'password',
            'email': 'newUser1@gmail.com',
            'inv_code': '12'
        }
        result = self.app.post('/add_user_with_class', data=newUser)
        assert result.status_code == 200

        newUser = {
            'username': 'newUser2',
            'password': '',
            'email': 'newUser1@gmail.com',
            'inv_code': '12'
        }
        result = self.app.post('/add_user_with_class', data=newUser)
        assert result.status_code == 400
        # Get list of users in a class
        result = self.app.get('/get_users_from_class/1?session=' + rv.data.decode('utf-8'))
        assert result.status_code == 200
        result = json.loads(result.data)
        assert result[0]['name'] == 'newUser1'

        # Get individual user
        result = self.app.get('/get_user_info/'+str(result[0]['id'])+"?session="+ rv.data.decode('utf-8'))
        assert result.status_code == 200
        result = json.loads(result.data)
        assert result['name'] == 'newUser1'

        # User that doesn't exists
        result = self.app.get('/get_user_info/55?session=' + rv.data.decode('utf-8'))
        assert result.status_code == 401


    def test_remove_class(self):
        userDictionary = {
            'username': 'testUser1',
            'password': 'password'
        }
        rv = self.api_post('/add_user/test3210@gmail.com', userDictionary)
        classDictionary = {
            'inv_code': '12',
            'class_name': 'FrenchB1',
            'class_language_id': 'fr',
            'max_students': '10'
        }
        result = self.app.post('/add_class?session=' + rv.data.decode('utf-8'), data=classDictionary)
        assert result.status_code == 200
        # Remove class that teacher owns
        result = self.app.post('/remove_class/1?session=' + rv.data.decode('utf-8'))
        assert result.status_code == 200
        # Try to remove class that is already removed
        result = self.app.post('/remove_class/1?session=' + rv.data.decode('utf-8'))
        assert result.status_code == 401

    def test_update_class(self):
        userDictionary = {
            'username': 'testUser1',
            'password': 'password'
        }
        rv = self.api_post('/add_user/test3210@gmail.com', userDictionary)
        classDictionary = {
            'inv_code': '12',
            'class_name': 'FrenchB1',
            'class_language_id': 'fr',
            'max_students': '10'
        }
        result = self.app.post('/add_class?session=' + rv.data.decode('utf-8'), data=classDictionary)


        # Test valid update
        updateDictionary = {
            'inv_code':'123',
            'class_name':'SpanishB1',
            'max_students':'11'
        }
        result = self.app.post('/update_class/1?session='+ rv.data.decode('utf-8'), data=updateDictionary)
        assert result.status_code == 200
        result = self.app.get('/get_class_info/1?session='+ rv.data.decode('utf-8'))
        assert result.status_code == 200
        loaded = json.loads(result.data)
        assert loaded['class_name'] == 'SpanishB1'
        assert loaded['max_students'] == 11
        assert loaded['inv_code'] == '123'


        # Test invalid update (negative max students)
        updateDictionary = {
            'inv_code': '123',
            'class_name': 'SpanishB1',
            'max_students': '-11'
        }
        result = self.app.post('/update_class/1?session=' + rv.data.decode('utf-8'), data=updateDictionary)
        assert result.status_code == 400
        result = self.app.get('/get_class_info/1?session=' + rv.data.decode('utf-8'))
        loaded = json.loads(result.data)
        assert loaded['max_students'] == 11

        # Add second teacher to create new class
        userDictionary = {
            'username': 'testUser2',
            'password': 'password'
        }
        rv2 = self.api_post('/add_user/test321230@gmail.com', userDictionary)
        # Add class with ID that another class used to have
        classDictionary = {
            'inv_code': '12',
            'class_name': 'FrenchB1',
            'class_language_id': 'fr',
            'max_students': '10'
        }
        result = self.app.post('/add_class?session=' + rv2.data.decode('utf-8'), data=classDictionary)
        assert result.status_code == 200

        # Test invalid update (taken inv code)
        updateDictionary = {
            'inv_code': '12',
            'class_name': 'SpanishB1',
            'max_students': '11'
        }
        result = self.app.post('/update_class/1?session=' + rv.data.decode('utf-8'), data=updateDictionary)
        assert result.status_code == 400

        # Test invalid permissions
        updateDictionary = {
            'inv_code': '1245',
            'class_name': 'SpanishB1',
            'max_students': '11'
        }
        result = self.app.post('/update_class/2?session=' + rv.data.decode('utf-8'), data=updateDictionary)
        assert result.status_code == 401