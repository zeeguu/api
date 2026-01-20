from datetime import datetime

from zeeguu.core.model import User
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson

from zeeguu.core.util.encoding import datetime_to_json
from zeeguu.core.util.time import human_readable_duration, human_readable_date
from zeeguu.core.model.db import db

VERY_FAR_IN_THE_PAST = "2000-01-01T00:00:00"
VERY_FAR_IN_THE_FUTURE = "9999-12-31T23:59:59"


class UserListeningSession(db.Model):
    """
    This class keeps track of the user's audio lesson listening sessions.
    So we can study how much time the user spends listening to audio lessons.
    """

    __table_args__ = dict(mysql_collate="utf8_bin")
    __tablename__ = "user_listening_session"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    daily_audio_lesson_id = db.Column(db.Integer, db.ForeignKey(DailyAudioLesson.id))
    daily_audio_lesson = db.relationship(DailyAudioLesson)

    start_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # Duration time in milliseconds
    last_action_time = db.Column(db.DateTime)

    is_active = db.Column(db.Boolean)
    platform = db.Column(db.SmallInteger)

    def __init__(self, user_id, daily_audio_lesson_id, current_time=None, platform=None):
        self.user_id = user_id
        self.daily_audio_lesson_id = daily_audio_lesson_id
        self.is_active = True
        self.platform = platform

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
    def _create_new_session(db_session, user_id, daily_audio_lesson_id, current_time=None, platform=None):
        """
        Creates a new listening session

        Parameters:
        user_id = user identifier
        daily_audio_lesson_id = audio lesson identifier
        current_time = optional override for the current time
        platform = platform identifier (see constants.py PLATFORM_*)
        """
        if current_time is None:
            current_time = datetime.now()

        listening_session = UserListeningSession(user_id, daily_audio_lesson_id, current_time, platform)
        db_session.add(listening_session)
        db_session.commit()
        return listening_session

    @classmethod
    def find_by_user(
        cls,
        user_id,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
        is_active: bool = None,
    ):
        """
        Get listening sessions by user

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
    def find_by_user_and_language(
        cls,
        user_id,
        language_id,
        from_date: str = VERY_FAR_IN_THE_PAST,
        to_date: str = VERY_FAR_IN_THE_FUTURE,
    ):
        """
        Get listening sessions by user and language

        return: list of sessions
        """
        query = (
            cls.query.join(DailyAudioLesson)
            .filter(cls.user_id == user_id)
            .filter(DailyAudioLesson.language_id == language_id)
            .filter(cls.start_time >= from_date)
            .filter(cls.start_time <= to_date)
            .order_by(cls.start_time)
        )

        return query.all()

    @classmethod
    def find_by_lesson(cls, daily_audio_lesson_id):
        """
        Get all listening sessions for a specific lesson

        return: list of sessions
        """
        return cls.query.filter(cls.daily_audio_lesson_id == daily_audio_lesson_id).all()

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "daily_audio_lesson_id": self.daily_audio_lesson_id,
            "duration": self.duration,
            "start_time": datetime_to_json(self.start_time),
            "last_action_time": datetime_to_json(self.last_action_time),
            "is_active": self.is_active,
        }
