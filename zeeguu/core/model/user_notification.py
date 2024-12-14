import sqlalchemy

from zeeguu.core.model import db
from zeeguu.core.model.user import User
from zeeguu.core.model.notification import Notification
from datetime import datetime


class UserNotification(db.Model):
    """
    A Notification that was sent to the user.
    If the user clicks it, the notification_click_time will have the datetime
    when that click was performed. IF not, this field will be null

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    notification_id = db.Column(db.Integer, db.ForeignKey(Notification.id))
    notification_date = db.Column(db.DateTime)
    notification_click_time = db.Column(db.DateTime, nullable=True)

    def __init__(self, user_id, notification_id):
        self.user_id = user_id
        self.notification_id = notification_id
        self.notification_date = datetime.now()

    def __repr__(self):
        return f"<UserNotification({self.id}): User: {self.user_id}, Notification: {self.notification_id}>"

    @classmethod
    def find_by_id(cls, i):
        try:
            notification = cls.query.filter(cls.id == i).one()
            return notification
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            return None

    @classmethod
    def get_all_notifications_for_user(cls, user_id):
        try:
            user_notification = cls.query.filter(cls.user_id == user_id).all()
            return user_notification
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def create_user_notification(cls, user_id, notification_id, db_session):
        user_notification = UserNotification(user_id, notification_id)
        db_session.add(user_notification)
        return user_notification

    @classmethod
    def update_user_notification_time(cls, user_notification_id, db_session):
        user_notification = cls.find_by_id(user_notification_id)
        user_notification.notification_click_time = datetime.now()
        db_session.add(user_notification)
        return user_notification
