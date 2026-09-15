import datetime
import uuid

from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from zeeguu.core.model.user import User
from zeeguu.logging import warning

from zeeguu.core.model.db import db


class Session(db.Model):
    # Named for the index 26-09-11--dedupe_and_unique_session_uuid.sql adds in
    # production, so nobody generates a second one. Production has never had it,
    # which is how a duplicated authentication token came to exist there.
    __table_args__ = (
        db.UniqueConstraint("uuid", name="unique_session_uuid"),
        {"mysql_collate": "utf8_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)
    last_use = db.Column(db.DateTime)
    uuid = db.Column(db.String(36), nullable=False)

    def __init__(self, user, _uuid: str):
        self.uuid = _uuid
        self.user = user
        self.update_use_date()

    def update_use_date(self):
        self.last_use = datetime.datetime.now()

    @classmethod
    def get_last_use_for_user(cls, user_id):
        try:
            return (
                cls.query.filter(cls.user_id == user_id)
                .order_by(cls.last_use.desc())
                .limit(1)
                .one()
            ).last_use
        except NoResultFound:
            return None

    @classmethod
    def create_for_user(cls, user):
        # The collision check used to be cls.query.get(_uuid), which is a PRIMARY
        # KEY lookup -- and the primary key here is the integer id, not the uuid.
        # It asked "is there a session whose id equals this hex string", which is
        # never true, so it never checked anything. Filter on the column instead.
        _uuid = uuid.uuid4().hex
        while cls.query.filter(cls.uuid == _uuid).first() is not None:
            _uuid = uuid.uuid4().hex
        return cls(user, _uuid)

    @classmethod
    def find(cls, _uuid: str = None):
        # gets the session object for a given uuid

        try:
            object_from_db = cls.query.filter(cls.uuid == _uuid).one()

            return object_from_db
        except NoResultFound:
            return None
        except MultipleResultsFound:
            # Only NoResultFound used to be caught, so a duplicated uuid raised
            # out of here and every request carrying that token 500'd. Production
            # had one such pair, because it has no unique index on the column.
            #
            # Refuse rather than pick: the rows may belong to different users, and
            # returning either would authenticate the wrong one. Returning None
            # reads as an expired session, so the client logs in again and gets a
            # fresh uuid.
            # Only a prefix: the uuid is a live credential and does not belong
            # in the logs, but enough of it has to be there to find the rows.
            warning(f"Duplicate session uuid; refusing it: {str(_uuid)[:8]}...")
            return None
