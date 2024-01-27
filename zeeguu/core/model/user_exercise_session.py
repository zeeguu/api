import sqlalchemy
import zeeguu.core

from datetime import datetime, timedelta
from zeeguu.core.model.user import User

from zeeguu.core.model import db

VERY_FAR_IN_THE_PAST = "2000-01-01T00:00:00"
VERY_FAR_IN_THE_FUTURE = "9999-12-31T23:59:59"


class UserExerciseSession(db.Model):
    """
    This class keeps track of the user's exercise sessions.

    So we can study how much time and when the user has done exercises.
    """

    __table_args__ = dict(mysql_collate="utf8_bin")
    __tablename__ = "user_exercise_session"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    start_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # Duration time in miliseconds
    last_action_time = db.Column(db.DateTime)

    is_active = db.Column(db.Boolean)

    def __init__(self, user_id, start_time, current_time=None):
        self.user_id = user_id
        self.is_active = False

        # When we want to emulate an event happening in a particular moment in the past or in the future,
        #   we can provide the current_time variable to override the datetime.now()
        if current_time is None:
            current_time = datetime.now()

        self.start_time = start_time
        self.last_action_time = current_time

        duration = self.last_action_time - self.start_time
        self.duration = duration.total_seconds() * 1000

    def exercises_in_session_string(self):
        from zeeguu.core.sql.learner.exercises_history import exercises_in_session

        exercise_details_list = exercises_in_session(self.id)

        res = ""
        for each in exercise_details_list:
            res += f"{each['time']} {int(each['solving_speed'] / 1000):>6} {each['outcome']:>6} {each['word']:<15} {each['source']}   \n"

        return res

    @classmethod
    def find_by_user_id(
        cls,
        user_id,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
    ):
        """

        Get exercise sessions by user

        return: object or None if not found
        """
        query = cls.query
        query = query.filter(cls.user_id == user_id)
        query = query.filter(cls.start_time >= from_date)
        query = query.filter(cls.start_time <= to_date)

        query = query.order_by("start_time")

        sessions = query.all()
        return sessions

    @classmethod
    def find_by_id(cls, id):
        query = cls.query
        query = query.filter(cls.id == id)
        return query.one()

    @classmethod
    def find_by_cohort(
        cls,
        cohort_id,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
    ):
        """
        Get exercise sessions by cohort
        return: object or None if not found
        """
        query = cls.query.join(User).filter(User.cohort_id == cohort_id)
        query = query.filter(cls.start_time >= from_date)
        query = query.filter(cls.start_time <= to_date)

        query = query.order_by("start_time")

        sessions = query.all()
        return sessions
