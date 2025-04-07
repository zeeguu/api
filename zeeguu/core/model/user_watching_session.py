from datetime import datetime
from zeeguu.core.model import db, User, Video
from zeeguu.core.constants import *
from zeeguu.core.util.encoding import datetime_to_json

VERY_FAR_IN_THE_PAST = "2000-01-01T00:00:00"
VERY_FAR_IN_THE_FUTURE = "9999-12-31T23:59:59"

class UserWatchingSession(db.Model):
    """
    This class keeps track of the user's watching sessions.
    So we can study how much time, when and which videos the user has watched.
    """

    __table_args__ = dict(mysql_collate="utf8_bin")
    __tablename__ = "user_watching_session"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    video_id = db.Column(db.Integer, db.ForeignKey(Video.id))
    video = db.relationship(Video)

    start_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # Duration time in milliseconds
    last_action_time = db.Column(db.DateTime)

    is_active = db.Column(db.Boolean)

    def __init__(self, user_id, video_id, current_time=None):
        self.user_id = user_id
        self.video_id = video_id
        self.is_active = True

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
            UserActivityData.query,filter(UserActivityData.time > self.start_time)
            .filter(UserActivityData.time < self.last_action_time)
            .all()
        )
    
    @staticmethod
    def get_wathching_session_timeout():
        return WATCHING_SESSION_TIMEOUT
    
    @classmethod
    def find_by_id(cls, session_id):
        return cls.query.filter(cls.id == session_id).one()
    
    @classmethod
    def _create_new_session(
        db_session, user_id, video_id, current_time=datetime.now()
    ):
        watching_session = UserWatchingSession(user_id, video_id, current_time)
        db_session.add(watching_session)
        db_session.commit()
        return watching_session
    
    @classmethod
    def find_by_user(
        cls,
        user_id,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
        is_active: bool = None,
    ):
        query = cls.query()
        query = query.filter(cls.user_id == user_id)
        query = query.filter(cls.start_time >= from_date)
        query = query.filter(cls.start_time <= to_date)
        if is_active is not None:
            query = query.filter(cls.is_active == is_active)
        query = query.order_by("start_time")

        sessions = query.all()
        return sessions

    @classmethod
    def get_total_watching_for_user_video(cls, user, video):
        try:
            return (
                db.session.query(sum(cls.duration))
                .filter(cls.user == user)
                .filter(cls.video == video)
                .one()
            )[0]
        except Exception as e:
            from sentry_sdk import capture_exception
            capture_exception(e)
            print(e)
            return 0
        
    @classmethod
    def find_by_video(
        cls,
        video,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
        is_active: bool = None,
        cohort: bool = None,
    ):
        from .user_cohort_map import UserCohortMap
        if cohort is not None:
            query = (
                cls.query.join(User)
                .join(UserCohortMap)
                .filter(UserCohortMap.cohort_id == cohort)
            )
        else:
            query = cls.query
        query = query.filter(cls.video_id == video)
        query = query.filter(cls.start_time >= from_date)
        query = query.filter(cls.start_time <= to_date)
        if is_active is not None:
            query = query.filter(cls.is_active == is_active)

        query = query.order_by("start_time")
        sessions = query.all()
        return sessions
    
    @classmethod
    def find_by_user_and_video(
        cls,
        user,
        video,
    ):
        query = cls.query
        query = query.filter(cls.user_id == user.id)
        query = query.filter(cls.video_id == video.id)

        query = query.order_by("start_time")
        sessions = query.all()
        return sessions
    
    @classmethod
    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "video_id": self.video_id,
            "start_time": datetime_to_json(self.start_time),
            "duration": self.duration,
            "last_action_time": datetime_to_json(self.last_action_time),
            "is_active": self.is_active,
            "video_title": self.video.title,
        }