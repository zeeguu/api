from datetime import datetime

from zeeguu.core.model import User

from zeeguu.core.util.encoding import datetime_to_json
from zeeguu.core.util.time import human_readable_duration, human_readable_date
from zeeguu.core.model.db import db

VERY_FAR_IN_THE_PAST = "2000-01-01T00:00:00"
VERY_FAR_IN_THE_FUTURE = "9999-12-31T23:59:59"


class UserBrowsingSession(db.Model):
    """
    This class keeps track of the user's article browsing sessions.
    So we can study how much time the user spends browsing article lists.
    """

    __table_args__ = dict(mysql_collate="utf8_bin")
    __tablename__ = "user_browsing_session"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    start_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # Duration time in milliseconds
    last_action_time = db.Column(db.DateTime)

    is_active = db.Column(db.Boolean)

    def __init__(self, user_id, current_time=None):
        self.user_id = user_id
        self.is_active = True

        if current_time is None:
            current_time = datetime.now()

        self.start_time = current_time
        self.last_action_time = current_time
        self.duration = 0

    def human_readable_duration(self):
        return human_readable_duration(self.duration)

    def human_readable_date(self):
        return human_readable_date(self.start_time)

    @classmethod
    def find_by_id(cls, session_id):
        return cls.query.filter(cls.id == session_id).one()

    @staticmethod
    def _create_new_session(db_session, user_id, current_time=None):
        """
        Creates a new browsing session

        Parameters:
        user_id = user identifier
        current_time = optional override for the current time
        """
        if current_time is None:
            current_time = datetime.now()

        browsing_session = UserBrowsingSession(user_id, current_time)
        db_session.add(browsing_session)
        db_session.commit()
        return browsing_session

    @classmethod
    def find_by_user(
        cls,
        user_id,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
        is_active: bool = None,
    ):
        """
        Get browsing sessions by user

        return: list of sessions
        """
        query = cls.query
        query = query.filter(cls.user_id == user_id)
        query = query.filter(cls.start_time >= from_date)
        query = query.filter(cls.start_time <= to_date)

        if is_active is not None:
            query = query.filter(cls.is_active == is_active)

        query = query.order_by("start_time")

        sessions = query.all()
        return sessions

    @classmethod
    def find_by_cohort(
        cls,
        cohort_id,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
        is_active: bool = None,
    ):
        """
        Get browsing sessions by cohort

        return: list of sessions
        """
        from .user_cohort_map import UserCohortMap

        query = (
            cls.query.join(User)
            .join(UserCohortMap)
            .filter(UserCohortMap.cohort_id == cohort_id)
        )
        query = query.filter(cls.start_time >= from_date)
        query = query.filter(cls.start_time <= to_date)

        if is_active is not None:
            query = query.filter(cls.is_active == is_active)

        query = query.order_by("start_time")

        sessions = query.all()
        return sessions

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "duration": self.duration,
            "start_time": datetime_to_json(self.start_time),
            "last_action_time": datetime_to_json(self.last_action_time),
            "is_active": self.is_active,
        }
