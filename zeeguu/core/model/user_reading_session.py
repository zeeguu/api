import sqlalchemy
import zeeguu.core

from datetime import datetime, timedelta

from zeeguu.core.model import User, Article

from zeeguu.core.constants import *
from zeeguu.core.util.encoding import datetime_to_json

from zeeguu.core.model import db

VERY_FAR_IN_THE_PAST = "2000-01-01T00:00:00"
VERY_FAR_IN_THE_FUTURE = "9999-12-31T23:59:59"


def is_opening_or_interactive_event(event):
    opening_or_interactive = (
        LEGACY_OPENING + OPENING_ACTIONS + LEGACY_INTERACTION + INTERACTION_ACTIONS
    )

    return event in opening_or_interactive


def is_closing_event(event):
    return event in CLOSING_ACTIONS or event in LEGACY_CLOSING


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

    @classmethod
    def _find_most_recent_session(cls, user_id, article_id, db_session):
        """
        Queries and returns if there is an open reading session for that user and article

        parameters:
        user_id = user identifier
        article_id = article identifier
        db_session = database session

        returns: the active reading_session record for the specific user and article or None if none is found

        Note: if article_id is None, returns most recent session
        """
        query = cls.query
        query = query.filter(cls.user_id == user_id)
        query = query.filter(cls.is_active == True)

        if article_id:
            query = query.filter(cls.article_id == article_id)

        try:
            return query.one()

        # Some events do not have a url, therefore we don't know the article
        #  in those cases, we continue the last open session
        except sqlalchemy.orm.exc.MultipleResultsFound:
            query.order_by(UserReadingSession.last_action_time)
            # Close all open sessions except last one
            open_sessions = query.with_for_update().all()
            for reading_session in open_sessions[:-1]:
                reading_session._close_reading_session(db_session)
            return open_sessions[-1]

        except sqlalchemy.orm.exc.NoResultFound:
            return None

    def _is_still_active(self, current_time=datetime.now()):
        """
        Validates if the reading session is still valid (according to the reading_session_timeout control variable)

        Parameters:
        current_time = when this parameter is sent, instead of using the datetime.now() value for the current time
                    we use the provided value as the system time (only used for filling in historical data)

        returns: True if the time between the reading session's last action and the current time
                is less or equal than the reading_session_timeout
        """
        time_difference = current_time - self.last_action_time
        w_reading_session_timeout = timedelta(minutes=READING_SESSION_TIMEOUT)

        return time_difference <= w_reading_session_timeout

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

    def _update_last_action_time(
        self, db_session, add_grace_time=False, current_time=datetime.now()
    ):
        """
        Updates the last_action_time field. For sessions that were left open, since we cannot know exactly
        when the user stopped using it, we give an additional (reading_session_timeout) time benefit

        Parameters:
        db_session = database session
        add_grace_time = True/False boolean value to add an extra reading_session_timeout minutes after the last_action_datetime
        current_time = when this parameter is sent, instead of using the datetime.now() value for the current time
                    we use the provided value as the system time (only used for filling in historical data)

        returns: The reading session
        """

        if add_grace_time:
            self.last_action_time += timedelta(minutes=READING_SESSION_TIMEOUT)
        else:
            self.last_action_time = current_time

            # update the duration too
            current_session_length = current_time - self.start_time
            self.duration = (
                current_session_length.total_seconds() * 1000
            )  # Convert to miliseconds

        try:
            db_session.add(self)
            db_session.commit()
        except:
            import traceback

            traceback.print_exc()
            print(self.id)
        return self

    def _close_reading_session(self, db_session):
        """
        Computes the duration of the reading session and sets the is_active field to False

        Parameters:
        db_session = database session

        returns: The reading session or None if none is found

        Note: If duration is zero, the session is deleted
        """
        time_diff = self.last_action_time - self.start_time
        if time_diff.total_seconds() == 0:
            db_session.delete(self)
        else:
            self.is_active = False
            self.duration = time_diff.total_seconds() * 1000  # Convert to miliseconds
            db_session.add(self)
        db_session.commit()
        return self

    # NOTE:  Because not all opening session actions end with a closing action,
    # whenever we open a new session, we call this method to close all other active sessions,
    # and to avoid having active sessions forever (or until the user re-opens the same article)
    @classmethod
    def _close_user_reading_sessions(cls, db_session, user_id):
        """
        Finds and closes all open sessions from a specific user

        Parameters:
        db_session = database session
        user_id = user identifier to close his sessions

        returns: None

        Note: If duration is zero, the session is deleted
        """
        query = cls.query
        query = query.filter(cls.user_id == user_id)
        query = query.filter(cls.is_active == True)
        reading_sessions = query.with_for_update().all()
        for reading_session in reading_sessions:
            time_diff = reading_session.last_action_time - reading_session.start_time
            # If the duration is zero, we delete the session
            # This can happen when the user opens a session and does nothing afterwards,
            # so the timeout closes the session with a duration of zero
            if time_diff.total_seconds() == 0:
                db_session.delete(reading_session)
            else:
                reading_session.is_active = False
                reading_session.duration = (
                    time_diff.total_seconds() * 1000
                )  # Convert to miliseconds
                db_session.add(reading_session)
            db_session.commit()
        return None

    @classmethod
    def close_all_stale_reading_sessions(cls, db_session):
        """
        Finds and closes all open sessions
        that are older than the reading_session_timeout

        Parameters:
        db_session = database session

        returns: None

        Note: If duration is zero, the session is deleted
        """
        query = cls.query
        query = query.filter(cls.is_active == True)
        reading_sessions = query.with_for_update().all()
        for reading_session in reading_sessions:
            if reading_session._is_still_active():
                print(f"skipping session: {reading_session.id} because it's too recent")
                continue

            time_diff = reading_session.last_action_time - reading_session.start_time
            # If the duration is zero, we delete the session
            # This can happen when the user opens a session and does nothing afterwards,
            # so the timeout closes the session with a duration of zero
            if time_diff.total_seconds() == 0:
                print(f"deleting session: {reading_session.id} because it's zero sized")
                db_session.delete(reading_session)

            else:
                reading_session.is_active = False
                reading_session.duration = time_diff.total_seconds() * 1000
                print(
                    f"closing session: {reading_session.id} with duration: {reading_session.duration} because it's too old"
                )

                db_session.add(reading_session)
        db_session.commit()

    @classmethod
    def update_reading_session(
        cls, db_session, event, user_id, article_id, current_time=datetime.now()
    ):
        """
        Main callable method that keeps track of the reading sessions.
        Depending if the event belongs to the opening, interaction or closing list of events
        the method creates, updates or closes a reading session

        Parameters:
        db_session = database session
        event = event string (based on the user_activity_data events,
                                check list at the beginning of this python file)
        user_id = user identifier
        article_id = article identifier
        current_time = when this parameter is sent, instead of using the datetime.now() value for the current time
                    we use the provided value as the system time (only used for filling in historical data)

        returns: The reading session  or None if none is found
        """
        most_recent_reading_session = cls._find_most_recent_session(
            user_id, article_id, db_session
        )

        if is_opening_or_interactive_event(event):
            if not most_recent_reading_session:  # If there is no active reading session
                UserReadingSession._close_user_reading_sessions(db_session, user_id)
                return cls._create_new_session(
                    db_session, user_id, article_id, current_time
                )

            else:  # Is there an active reading session
                # If the open reading session is still valid (within the reading_session_timeout window)
                if most_recent_reading_session._is_still_active(current_time):
                    return most_recent_reading_session._update_last_action_time(
                        db_session, add_grace_time=False, current_time=current_time
                    )
                # There is an open reading session but the elapsed time is larger than the reading_session_timeout
                else:
                    most_recent_reading_session._update_last_action_time(
                        db_session, add_grace_time=True, current_time=current_time
                    )
                    most_recent_reading_session._close_reading_session(db_session)
                    UserReadingSession._close_user_reading_sessions(db_session, user_id)
                    return cls._create_new_session(
                        db_session, user_id, article_id, current_time
                    )

        elif is_closing_event(event):
            if most_recent_reading_session:  # If there is an open reading session
                # If the elapsed time is shorter than the timeout parameter
                if most_recent_reading_session._is_still_active(current_time):
                    most_recent_reading_session._update_last_action_time(
                        db_session, add_grace_time=False, current_time=current_time
                    )
                # When the elapsed time is larger than the reading_session_timeout,
                # we add the grace time (which is n extra minutes where n=reading_session_timeout)
                else:
                    most_recent_reading_session._update_last_action_time(
                        db_session, add_grace_time=True, current_time=current_time
                    )
                return most_recent_reading_session._close_reading_session(db_session)
            else:  # If there is no open reading session for the specified article,
                # we close all the articles from the user
                UserReadingSession._close_user_reading_sessions(db_session, user_id)
                return None
        else:
            return None

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
        query = cls.query.join(User).filter(User.cohort_id == cohort)
        query = query.filter(UserReadingSession.start_time >= from_date)
        query = query.filter(UserReadingSession.start_time <= to_date)

        if is_active is not None:
            query = query.filter(cls.is_active == is_active)
        query = query.order_by("start_time")

        sessions = query.all()
        return sessions

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
        if cohort is not None:
            query = cls.query.join(User).filter(User.cohort_id == cohort)
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

    def json_serializable_dict(self):
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
