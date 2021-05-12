from unittest import TestCase
from zeeguu_core_test.model_test_mixin import ModelTestMixIn
import zeeguu_core
from zeeguu_core_test.rules.user_reading_session_rule import ReadingSessionRule
from zeeguu_core.constants import UMR_OPEN_ARTICLE_ACTION, UMR_ARTICLE_CLOSED_ACTION
from zeeguu_core.model.user_reading_session import UserReadingSession
from datetime import datetime, timedelta

db_session = zeeguu_core.db.session


class UserReadingSessionTest(ModelTestMixIn, TestCase):

    def setUp(self):
        super().setUp()
        self.read_session = ReadingSessionRule().w_session
        self.reading_session_timeout = UserReadingSession.get_reading_session_timeout()
        self.VERY_FAR_IN_THE_PAST = '2000-01-01T00:00:00'
        self.VERY_FAR_IN_THE_FUTURE = '2030-01-01T00:00:00'
        self.TIMEOUT_MINUTES_IN_THE_PAST = datetime.now() - timedelta(minutes=self.reading_session_timeout)
        self.TWICE_TIMEOUT_MINUTES_IN_THE_PAST = datetime.now() - timedelta(minutes=self.reading_session_timeout * 2)

    # One result scenario
    def test__get_reading_session1(self):
        #Since the read_session1 rule saves the exercise_session in the DB, we expect to find it there
        assert UserReadingSession._find_most_recent_session(self.read_session.user_id, self.read_session.article_id, db_session)

    # Many results scenario
    def test__get_reading_session2(self):
        self.read_session2 = ReadingSessionRule().w_session
        self.read_session2.user_id = self.read_session.user_id
        self.read_session2.article_id = self.read_session.article_id
        assert UserReadingSession._find_most_recent_session(self.read_session.user_id, self.read_session.article_id, db_session)
        
    def test__is_same_reading_session(self):
        self.read_session.last_action_time = self.TIMEOUT_MINUTES_IN_THE_PAST
        assert (True == self.read_session._is_still_active())

    def test__is_not_same_reading_session(self):
        self.read_session.last_action_time = self.TWICE_TIMEOUT_MINUTES_IN_THE_PAST
        assert (False == self.read_session._is_still_active())

    # One result scenario (add grace time)
    def test__update_last_use1(self):
        assert self.read_session == self.read_session._update_last_action_time(db_session, add_grace_time=True)

    # One result scenario (no grace time)
    def test__update_last_use2(self):
        assert self.read_session == self.read_session._update_last_action_time(db_session, add_grace_time=False)

    def test__close_session(self):
        assert self.read_session._close_reading_session(db_session)

    def test__close_user_sessions(self):
        assert (None == UserReadingSession._close_user_reading_sessions(db_session, self.read_session.user_id))

    # Open action / different session
    def test__update_reading_session_scenario1(self):
        event = UMR_OPEN_ARTICLE_ACTION
        self.read_session.is_active = False
        resulting_reading_session =  UserReadingSession.update_reading_session(db_session, 
                                                            event, 
                                                            self.read_session.user_id, 
                                                            self.read_session.article_id
                                                        )
        assert resulting_reading_session != self.read_session

    # Open action / open and same session
    def test__update_reading_session_scenario2(self):
        self.read_session.last_action_time = self.TIMEOUT_MINUTES_IN_THE_PAST
        event = UMR_OPEN_ARTICLE_ACTION
        resulting_reading_session =  UserReadingSession.update_reading_session(db_session, 
                                                            event, 
                                                            self.read_session.user_id, 
                                                            self.read_session.article_id
                                                        )
        assert resulting_reading_session == self.read_session

    # Open action / open but different/older session
    def test__update_reading_session_scenario3(self):
        event = UMR_OPEN_ARTICLE_ACTION
        self.read_session.last_action_time = self.TWICE_TIMEOUT_MINUTES_IN_THE_PAST
        resulting_reading_session = UserReadingSession.update_reading_session(db_session, 
                                                            event, 
                                                            self.read_session.user_id, 
                                                            self.read_session.article_id
                                                        )
        assert resulting_reading_session != self.read_session

    # Closing action / active and same reading session
    def test__update_reading_session_scenario4(self):
        event = UMR_ARTICLE_CLOSED_ACTION
        resulting_reading_session = UserReadingSession.update_reading_session(db_session, 
                                                            event, 
                                                            self.read_session.user_id, 
                                                            self.read_session.article_id
                                                        )
        assert (resulting_reading_session == self.read_session) and (self.read_session.is_active == False)

    # Closing action / active but different reading session
    def test__update_reading_session_scenario5(self):
        event = UMR_ARTICLE_CLOSED_ACTION
        self.read_session.last_action_time = self.TWICE_TIMEOUT_MINUTES_IN_THE_PAST
        resulting_reading_session = UserReadingSession.update_reading_session(db_session, 
                                                            event, 
                                                            self.read_session.user_id, 
                                                            self.read_session.article_id
                                                        )
        assert (resulting_reading_session == self.read_session and resulting_reading_session.is_active == False)

    def test__find_by_user(self):
        user = self.read_session.user
        active_sessions = UserReadingSession.find_by_user(user.id, self.VERY_FAR_IN_THE_PAST, self.VERY_FAR_IN_THE_FUTURE, True)
        assert active_sessions

    def test__find_by_cohort(self):
        cohort_id = self.read_session.user.cohort_id
        active_sessions = UserReadingSession.find_by_cohort(cohort_id, self.VERY_FAR_IN_THE_PAST, self.VERY_FAR_IN_THE_FUTURE,
                                                           True)
        assert active_sessions

    # Cohort_id provided
    def test__find_by_article_scenario1(self):
        article_id = self.read_session.article_id
        cohort_id = self.read_session.user.cohort_id
        active_sessions = UserReadingSession.find_by_article(article_id, self.VERY_FAR_IN_THE_PAST, self.VERY_FAR_IN_THE_FUTURE,
                                                            True, cohort_id)
        assert active_sessions

    # Empty cohort_id
    def test__find_by_article_scenario2(self):
        article_id = self.read_session.article_id
        active_sessions = UserReadingSession.find_by_article(article_id, self.VERY_FAR_IN_THE_PAST, self.VERY_FAR_IN_THE_FUTURE,
                                                            True)
        assert active_sessions

    def test__find_by_user_and_article(self):
        user_id = self.read_session.user_id
        article_id = self.read_session.article_id
        active_sessions = UserReadingSession.find_by_user_and_article(user_id, article_id)
        assert active_sessions

    def test_find_most_recent_session_with_empty_article(self):
        event = UMR_OPEN_ARTICLE_ACTION
        user_id = self.read_session.user_id
        article_id = None
        self.read_session.last_action_time = self.TIMEOUT_MINUTES_IN_THE_PAST
        resulting_reading_session = UserReadingSession.update_reading_session(db_session,
                                                                                 event, 
                                                                                 user_id, 
                                                                                 article_id
                                                                            )
        assert resulting_reading_session == self.read_session