from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship

from zeeguu.core.model.topic import Topic
from zeeguu.core.model.user import User

import zeeguu.core

from zeeguu.core.model.db import db
from zeeguu.core.model.race_safe import find_or_create


class TopicFilter(db.Model):
    """

    A topic filter is created when the user
    wants to filter out a particular topic.
    This is then taken into account in the
    mixed recomemnder, when retrieving articles.

    """

    # Named for the index tools/migrations/26-09-11--add_promised_unique_indexes.sql
    # adds in production, so nobody generates a second one. It is what
    # find_or_create's duplicate-entry branch exists for.
    __table_args__ = (
        db.UniqueConstraint("user_id", "topic_id", name="uq_topic_filter_user_topic"),
        {"mysql_collate": "utf8_bin"},
    )
    __tablename__ = "topic_filter"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = relationship(User)

    topic_id = db.Column(db.Integer, db.ForeignKey(Topic.id))
    topic = relationship(Topic)

    def __init__(self, user, topic):
        self.user = user
        self.topic = topic

    def __str__(self):
        return f"Topic filter ({self.user.name}, {self.topic})"

    __repr__ = __str__

    @classmethod
    def find_or_create(cls, session, user, topic):
        return find_or_create(
            session,
            cls,
            dict(user=user, topic=topic),
            lambda: cls(user, topic),
            commit=True,
        )

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
