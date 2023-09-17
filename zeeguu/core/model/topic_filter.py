from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship

from zeeguu.core.model.topic import Topic
from zeeguu.core.model.user import User
import sqlalchemy

import zeeguu.core

from zeeguu.core.model import db


class TopicFilter(db.Model):
    """

    A topic filter is created when the user
    wants to filter out a particular topic.
    This is then taken into account in the
    mixed recomemnder, when retrieving articles.

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "topic_filter"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = relationship(User)

    topic_id = db.Column(db.Integer, db.ForeignKey(Topic.id))
    topic = relationship(Topic)

    UniqueConstraint(user_id, topic_id)

    def __init__(self, user, topic):
        self.user = user
        self.topic = topic

    def __str__(self):
        return f"Topic filter ({self.user.name}, {self.topic})"

    __repr__ = __str__

    @classmethod
    def find_or_create(cls, session, user, topic):
        try:
            return cls.query.filter(cls.user == user).filter(cls.topic == topic).one()
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(user, topic)
            session.add(new)
            session.commit()
            return new

    @classmethod
    def all_for_user(cls, user):
        return cls.query.filter(cls.user == user).all()

    @classmethod
    def all_for_user_as_list(cls, user):
        return [topic_id for topic_id in cls.all_for_user()]

    @classmethod
    def with_id(cls, i):
        return (cls.query.filter(cls.id == i)).one()

    @classmethod
    def with_topic_id(cls, i, user):
        return (
            (cls.query.filter(cls.topic_id == i)).filter(cls.user_id == user.id).one()
        )
