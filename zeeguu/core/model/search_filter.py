from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from zeeguu.core.model.user import User

import sqlalchemy

import zeeguu.core

from zeeguu.core.model.db import db
from zeeguu.core.model.search import Search


class SearchFilter(db.Model):
    """

    A search filter is created when the user
    wants to filter out a particular search.
    This is then taken into account in the
    mixed recomemnder, when retrieving articles.

    """

    # Named for the index tools/migrations/26-09-11--add_promised_unique_indexes.sql
    # adds in production, so nobody generates a second one. It is what
    # find_or_create's duplicate-entry branch exists for.
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "search_id", name="uq_search_filter_user_search"
        ),
        {"mysql_collate": "utf8_bin"},
    )
    __tablename__ = "search_filter"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = relationship(User)

    from zeeguu.core.model.search import Search

    search_id = db.Column(db.Integer, db.ForeignKey(Search.id))
    search = relationship(Search)

    def __init__(self, user, search):
        self.user = user
        self.search = search

    def __str__(self):
        return f"Search filter ({self.user.name}, {self.search})"

    __repr__ = __str__

    @classmethod
    def find_or_create(cls, session, user, search):
        try:
            return cls.query.filter(cls.user == user).filter(cls.search == search).one()
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
                    new = cls(user, search)
                    session.add(new)
            except sqlalchemy.exc.IntegrityError:
                return (
                    cls.query.filter(cls.user == user)
                    .filter(cls.search == search)
                    .one()
                )
            session.commit()
            return new

    @classmethod
    def all_for_user(cls, user):
        return (
            cls.query.join(Search)
            .filter(cls.user == user)
            .filter(Search.language_id == user.learned_language_id)
            .all()
        )

    @classmethod
    def get_number_of_users_excluding(cls, search_id):
        return cls.query.filter(cls.search_id == search_id).count()

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
            return None
