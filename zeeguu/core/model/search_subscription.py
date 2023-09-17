from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from zeeguu.core.model.user import User
import sqlalchemy

import zeeguu.core

from zeeguu.core.model import db


class SearchSubscription(db.Model):
    """

    A search subscription is created when
    the user subscribed to a particular search.
    This is then taken into account in the
    mixed recomemmder, when retrieving articles.

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "search_subscription"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = relationship(User)

    from zeeguu.core.model.search import Search

    search_id = db.Column(db.Integer, db.ForeignKey(Search.id))
    search = relationship(Search)

    UniqueConstraint(user_id, search_id)

    def __init__(self, user, search):
        self.user = user
        self.search = search

    def __str__(self):
        return f"Search subscription ({self.user.name}, {self.search})"

    __repr__ = __str__

    @classmethod
    def find_or_create(cls, session, user, search):
        try:
            return cls.query.filter(cls.user == user).filter(cls.search == search).one()
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(user, search)
            session.add(new)
            session.commit()
            return new

    @classmethod
    def all_for_user(cls, user):
        return cls.query.filter(cls.user == user).all()

    @classmethod
    def with_search_id(cls, i, user):
        return (cls.query.filter(cls.search_id == i).filter(cls.user == user)).one()

    @classmethod
    def with_search(cls, search_id):
        try:
            return (cls.query.filter(cls.search_id == search_id)).one()
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            print(e)
            return None
