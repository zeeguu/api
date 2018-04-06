# coding=utf-8

from unittest import TestCase
from tests_zeeguu_api.api_test_mixin import APITestMixin
from tests_zeeguu.rules.working_session_rule import WorkingSessionRule
from datetime import datetime, timedelta
from random import randint

class UserWorkingSessionTests(APITestMixin, TestCase):

    def setUp(self):
        super().setUp()
        working_session = WorkingSessionRule().w_session
        self.user_id = working_session.user_id
        self.article_id = working_session.article_id
        self.is_active = working_session.is_active
        self.cohort_id = working_session.user.cohort_id

    def test_working_sessions_by_user(self):
        parameters = dict(
            user_id = self.user_id,
            from_date = (datetime.now() - timedelta(minutes=randint(75000, 75000))).isoformat(),
            to_date = datetime.now().isoformat(),
            is_active = self.is_active
        )
        assert (self.json_from_api_get('/working_sessions_by_user', other_args=parameters))

    def test_working_sessions_by_cohort(self):
        parameters = dict(
            cohort_id = self.cohort_id,
            from_date = (datetime.now() - timedelta(minutes=randint(75000, 75000))).isoformat(),
            to_date = datetime.now().isoformat(),
            is_active = self.is_active
        )
        assert (self.json_from_api_get('/working_sessions_by_cohort', other_args=parameters))

    def test_working_sessions_by_cohort_and_article(self):
        parameters = dict(
            cohort_id = self.cohort_id,
            article_id = self.article_id,
            from_date = (datetime.now() - timedelta(minutes=randint(75000, 75000))).isoformat(),
            to_date = datetime.now().isoformat(),
            is_active = self.is_active
        )
        assert (self.json_from_api_get('/working_sessions_by_cohort_and_article', other_args=parameters))
    def test_working_sessions_by_user_and_article(self):
        parameters = dict(
            user_id=self.user_id,
            article_id=self.article_id
        )
        assert (self.json_from_api_get('/working_sessions_by_user_and_article', other_args=parameters))

    