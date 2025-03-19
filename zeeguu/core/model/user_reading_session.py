from datetime import datetime

from zeeguu.core.model import User, Article

from zeeguu.core.constants import *
from zeeguu.core.util.encoding import datetime_to_json
from sqlalchemy.sql.functions import sum
from zeeguu.core.model import db

VERY_FAR_IN_THE_PAST = "2000-01-01T00:00:00"
VERY_FAR_IN_THE_FUTURE = "9999-12-31T23:59:59"


class UserReadingSession(db.Model):
    """
    This class keeps track of the user's reading sessions.
    So we can study how much time, when and which articles the user has read.
    """

    __table_args__ = dict(mysql_collate="utf8_bin")
    __tablename__ = "user_reading_session"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    article_id = db.Column(db.Integer, db.ForeignKey(Article.id))
    article = db.relationship(Article)

    start_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # Duration time in miliseconds
    last_action_time = db.Column(db.DateTime)

    is_active = db.Column(db.Boolean)

    def __init__(self, user_id, article_id, current_time=None):
        self.user_id = user_id
        self.article_id = article_id
        self.is_active = True

        # When we want to emulate an event happening in a particular moment in the past or in the future,
        #   we can provide the current_time variable to override the datetime.now()
        if current_time is None:
            current_time = datetime.now()

        self.start_time = current_time
        self.last_action_time = current_time
        self.duration = 0

    def human_readable_duration(self):
        return str(round(self.duration / 1000 / 60, 1)) + "min"

    def human_readable_date(self):
        return str(datetime.date(self.start_time))

    def events_in_this_session(self):
        from zeeguu.core.model import UserActivityData

        return (
            UserActivityData.query.filter(UserActivityData.time > self.start_time)
            .filter(UserActivityData.time < self.last_action_time)
            .all()
        )

    @staticmethod
    def get_reading_session_timeout():
        return READING_SESSION_TIMEOUT

    @classmethod
    def find_by_id(cls, session_id):
        return cls.query.filter(cls.id == session_id).one()

    @staticmethod
    def _create_new_session(
        db_session, user_id, article_id, current_time=datetime.now()
    ):
        """
         Creates a new reading session

         Parameters:
         user_id = user identifier
         article_id = article identifier
        self.read_session.article_idis sent, instead of using the datetime.now() value for the current time
        self.read_session.article_idue as the system time (only used for filling in historical data)
        """
        reading_session = UserReadingSession(user_id, article_id, current_time)
        db_session.add(reading_session)
        db_session.commit()
        return reading_session

    @classmethod
    def find_by_user(
        cls,
        user_id,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
        is_active: bool = None,
    ):
        """

        Get reading sessions by user

        return: object or None if not found
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
        cohort,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
        is_active: bool = None,
    ):
        """
        Get reading sessions by cohort
        return: object or None if not found
        """
        from .user_cohort_map import UserCohortMap

        query = (
            cls.query.join(User)
            .join(UserCohortMap)
            .filter(UserCohortMap.cohort_id == cohort)
        )
        query = query.filter(UserReadingSession.start_time >= from_date)
        query = query.filter(UserReadingSession.start_time <= to_date)

        if is_active is not None:
            query = query.filter(cls.is_active == is_active)
        query = query.order_by("start_time")

        sessions = query.all()
        return sessions

    @classmethod
    def get_total_reading_for_user_article(cls, article, user):
        try:
            return (
                db.session.query(sum(cls.duration))
                .filter(cls.article == article)
                .filter(cls.user == user)
                .one()
            )[0]
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            print(e)
            return 0

    @classmethod
    def find_by_article(
        cls,
        article,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
        is_active: bool = None,
        cohort: bool = None,
    ):
        """
        Get reading sessions by article
        return: object or None if not found
        """
        from .user_cohort_map import UserCohortMap

        if cohort is not None:
            query = (
                cls.query.join(User)
                .join(UserCohortMap)
                .filter(UserCohortMap.cohort_id == cohort)
            )
        else:
            query = cls.query
        query = query.filter(cls.article_id == article)
        query = query.filter(cls.start_time >= from_date)
        query = query.filter(cls.start_time <= to_date)

        if is_active is not None:
            query = query.filter(cls.is_active == is_active)

        query = query.order_by("start_time")

        sessions = query.all()
        return sessions

    @classmethod
    def find_by_user_and_article(cls, user, article):
        """
        Get reading sessions by user and article
        return: object or None if not found
        """
        query = cls.query
        query = query.filter(cls.user_id == user)
        query = query.filter(cls.article_id == article)

        query = query.order_by("start_time")

        sessions = query.all()
        return sessions

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "duration": self.duration,
            "article_id": self.article_id,
            "start_time": datetime_to_json(self.start_time),
            "last_action_time": datetime_to_json(self.last_action_time),
            "is_active": self.is_active,
            "article_title": self.article.title,
        }
