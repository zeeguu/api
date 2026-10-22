from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from zeeguu.core.model.user import User
import zeeguu.core

from zeeguu.core.model.db import db
from zeeguu.core.model.race_safe import find_or_create
from zeeguu.core.model.search import Search


class SearchSubscription(db.Model):
    """

    A search subscription is created when
    the user subscribed to a particular search.
    This is then taken into account in the
    mixed recomemmder, when retrieving articles.

    """

    # Named for the index tools/migrations/26-09-11--add_promised_unique_indexes.sql
    # adds in production, so nobody generates a second one. It is what
    # find_or_create's duplicate-entry branch exists for.
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "search_id", name="uq_search_subscription_user_search"
        ),
        {"mysql_collate": "utf8_bin"},
    )
    __tablename__ = "search_subscription"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = relationship(User)

    from zeeguu.core.model.search import Search

    search_id = db.Column(db.Integer, db.ForeignKey(Search.id))
    search = relationship(Search)

    receive_email = db.Column(db.Boolean, default=False)

    def __init__(self, user, search, receive_email=False):
        self.user = user
        self.search = search
        self.receive_email = receive_email

    def __str__(self):
        return f"Search subscription ({self.user.name}, {self.search}, {self.receive_email})"

    __repr__ = __str__

    def as_dictionary(self):

        return dict(
            id=self.search.id,
            search=self.search.keywords,
            receive_email=self.receive_email,
        )

    @classmethod
    def find_or_create(cls, session, user, search, receive_email):
        return find_or_create(
            session,
            cls,
            dict(user=user, search=search),
            lambda: cls(user, search, receive_email),
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
    def with_search_id(cls, i, user):
        return (cls.query.filter(cls.search_id == i).filter(cls.user == user)).one()

    @classmethod
    def get_number_of_subscribers(cls, search_id):
        return cls.query.filter(cls.search_id == search_id).count()

    @classmethod
    def update_receive_email(cls, session, user, search, receive_email):
        subscription = cls.query.filter(
            cls.user == user, cls.search == search
        ).one_or_none()
        if subscription:
            subscription.receive_email = receive_email
            session.commit()
            return subscription
        else:
            raise ValueError("There is no search subscription")
