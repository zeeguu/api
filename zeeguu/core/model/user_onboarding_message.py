import sqlalchemy

from zeeguu.core.model.db import db
from zeeguu.core.model.onboarding_message import OnboardingMessage
from zeeguu.core.model.user import User
from zeeguu.logging import log
from datetime import datetime

class UserOnboardingMessage(db.Model):
    """
    An onboarding message that was sent to the user.
    If the user clicks it, the message_click_time will have the datetime
    when that click was performed. IF not, this field will be null

    """
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    onboarding_message_id = db.Column(db.Integer, db.ForeignKey(OnboardingMessage.id))
    message_shown_time = db.Column(db.DateTime)
    message_click_time = db.Column(db.DateTime, nullable=True)

    def __init__(self, user_id, onboarding_message_id):
        self.user_id = user_id
        self.onboarding_message_id = onboarding_message_id

    def __repr__(self):
        return f"<UserOnboardingMessage({self.id}): User: {self.user_id}, OnboardingMessage: {self.onboarding_message_id}>"

    @classmethod
    def find_by_id(cls, i):
        try:
            onboarding_message = cls.query.filter(cls.id == i).one()
            return onboarding_message
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            return None
    
    @classmethod
    def get_all_onboarding_messages_for_user(cls, user_id):
        try:
            user_onboarding_message = cls.query.filter(cls.user_id == user_id).all()
            return user_onboarding_message
        except sqlalchemy.orm.exc.NoResultFound:
            return None
    
    @classmethod
    def create_user_onboarding_message(cls, user_id, onboarding_message_id, db_session):
        user_onboarding_message = UserOnboardingMessage(user_id, onboarding_message_id)
        db_session.add(user_onboarding_message)
        return user_onboarding_message
    
    @classmethod
    def set_message_shown_time(cls, user_onboarding_message_id, db_session):
        """Set the time when the message was shown to the user."""
        user_onboarding_message = cls.find_by_id(user_onboarding_message_id)
        if user_onboarding_message and user_onboarding_message.message_shown_time is None:
            user_onboarding_message.message_shown_time = datetime.now()
            db_session.add(user_onboarding_message)
        return user_onboarding_message

    @classmethod
    def find_by_user_and_message(cls, user_id, onboarding_message_id):
        return cls.query.filter_by(
            user_id=user_id,
            onboarding_message_id=onboarding_message_id,
        ).first()

    @classmethod
    def update_user_onboarding_message_time(cls, user_onboarding_message_id, db_session):
        """Set the time when the user clicked/dismissed the message."""
        user_onboarding_message = cls.find_by_id(user_onboarding_message_id)
        user_onboarding_message.message_click_time = datetime.now()
        db_session.add(user_onboarding_message)
        return user_onboarding_message
    
    @classmethod
    def find_or_create_for_user_and_message(cls, session, user_id, onboarding_message_id):
        """Find or create a record for a user-message pair."""
        existing = cls.query.filter_by(
            user_id=user_id,
            onboarding_message_id=onboarding_message_id
        ).first()
        
        if existing:
            return existing
        
        new_record = cls(user_id, onboarding_message_id)
        session.add(new_record)
        session.commit()
        log("Created new user onboarding message record")
        return new_record
    