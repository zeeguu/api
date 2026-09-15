from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship

from zeeguu.core.model.topic import Topic
from zeeguu.core.model.user import User
import sqlalchemy

import zeeguu.core

from zeeguu.core.model.db import db


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
        try:
            return cls.query.filter(cls.user == user).filter(cls.topic == topic).one()
        except sqlalchemy.orm.exc.NoResultFound:
            # Two requests that both miss the query above both insert, and the
            # unique key lets exactly one of them through. The savepoint is what
            # makes losing survivable: a failed flush leaves the whole session
            # needing a rollback, so recovering without one raises
            # PendingRollbackError and recovering with a full rollback discards
            # whatever the caller had pending. Rolling back to a savepoint undoes
            # this insert and nothing else.
            try:
                with session.begin_nested():
                    new = cls(user, topic)
                    session.add(new)
            except sqlalchemy.exc.IntegrityError:
                return (
                    cls.query.filter(cls.user == user)
                    .filter(cls.topic == topic)
                    .one()
                )
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
