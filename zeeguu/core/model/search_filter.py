from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from zeeguu.core.model.user import User

import zeeguu.core

from zeeguu.core.model.db import db
from zeeguu.core.model.race_safe import find_or_create
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
        return find_or_create(
            session,
            cls,
            dict(user=user, search=search),
            lambda: cls(user, search),
            commit=True,
        )

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
