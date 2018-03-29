
import json
from unittest import TestCase

from tests_zeeguu_api.api_test_mixin import APITestMixin

import zeeguu


class DashboardTest(APITestMixin, TestCase):


    #def test_adding_classes(self):



    def test_get_classes(self):
        from zeeguu_api.app import app
        self.app = app.test_client()
        userDictionary = {
            'username': 'testUser',
            'password': 'password'
        }
        rv = self.api_post('/add_user/test321@gmail.com', userDictionary)
        assert rv
        classDictionary = {
            'inv_code':'123',
            'class_name':'FrenchB1',
            'class_language_id':'fr',
            'max_students':'33'
        }
        self.app.post('/add_class?session='+rv.data.decode('utf-8'),data= classDictionary)
        classesJ = self.app.get('/get_classes?session='+rv.data.decode('utf-8'))
        assert classesJ
        classes = json.loads(classesJ.data)
        assert classes
        assert classes[0]['class_name'] == 'FrenchB1'




   # def test_get_users_from_class(self):


    #def test_get_user_data(self):


    def test_has_session(self):
        from zeeguu_api.app import app
        self.app = app.test_client()

        # TEST FOR FAKE SESSION
        result = self.app.get('/has_session?session=31235ds')
        result = json.loads(result.data)
        assert result==0

        # TEST FOR REAL SESSION
        userDictionary = {
            'username':'testUser',
            'password':'password'
        }
        rv = self.api_post('/add_user/test321@gmail.com', userDictionary)
        assert rv
        result = self.app.get('/has_session?session='+rv.data.decode('utf-8'))
        result = json.loads(result.data)
        assert result==1



