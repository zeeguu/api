from sqlalchemy import String, DateTime
from sqlalchemy.orm import relationship
from zeeguu.core.model.user import User
from zeeguu.core.model.url import Url
from zeeguu.core.model.feedback_component import FeedbackComponent
from zeeguu.core.util.time import get_server_time_utc

import sqlalchemy

import zeeguu.core

from zeeguu.core.model import db


class UserFeedbackReport(db.Model):
    """

    A search filter is created when the user
    wants to filter out a particular search.
    This is then taken into account in the
    mixed recomemnder, when retrieving articles.

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "user_feedback_report"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = relationship(User)

    feedback_component_id = db.Column(db.Integer, db.ForeignKey(FeedbackComponent.id))
    feedback_component = relationship(FeedbackComponent)

    message = db.Column(String(512))
    report_time = db.Column(DateTime)

    url_id = db.Column(db.Integer, db.ForeignKey(Url.id))
    url = relationship(Url)

    def __init__(
        self, user: User, feedback_component: FeedbackComponent, message: str, url: Url
    ):
        self.user = user
        self.feedback_component = feedback_component
        self.message = message
        self.report_time = get_server_time_utc()
        self.url = url

    def __str__(self):
        return f"User Feedback: ('{self.message}', {self.feedback_component.component_type})"

    __repr__ = __str__

    @classmethod
    def create(
        cls,
        session,
        user: User,
        feedback_component: FeedbackComponent,
        message: str,
        url: Url,
    ):
        new = cls(user, feedback_component, message, url)
        session.add(new)
        return new

    @classmethod
    def all_for_user(cls, user):
        return cls.query.filter(cls.user == user).all()

    @classmethod
    def with_feedback_component_id(cls, feedback_component_id):
        return (
            cls.query.filter(cls.feedback_component_id == feedback_component_id)
        ).all()
