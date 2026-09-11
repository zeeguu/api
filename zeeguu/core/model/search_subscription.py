from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from zeeguu.core.model.user import User
import sqlalchemy
import zeeguu.core

from zeeguu.core.model.db import db
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
                    new = cls(user, search, receive_email)
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
