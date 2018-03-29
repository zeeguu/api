
import json
from unittest import TestCase

from tests_zeeguu_api.api_test_mixin import APITestMixin

import zeeguu


class DashboardTest(APITestMixin, TestCase):


    #def test_adding_classes(self):



    #def test_get_classes(self):


   # def test_get_users_from_class(self):


    #def test_get_user_data(self):


    def test_has_session(self):
        from zeeguu_api.app import app
        data = {}
        result = self.app.get('has_session?session=31235ds', data)

        assert result==0
        userDictionary = {
            'username':'testUser',
            'password':'password'
        }
        rv = self.api_post('/add_user/test321@gmail.com', userDictionary)
        data = {}
        params = {'session':rv}
        result = self.app.get('/has_session?session='+params['session'], data, params)
        assert result==1



