import datetime
import random

import flask
from sqlalchemy.orm.exc import NoResultFound

import zeeguu.core
from sqlalchemy import desc

from zeeguu.core.model.user import User

from zeeguu.core.model import db


class Session(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)
    last_use = db.Column(db.DateTime)

    _cache = dict()

    def __init__(self, user, id_):
        self.id = id_
        self.user = user
        self.update_use_date()

    def update_use_date(self):
        self.last_use = datetime.datetime.now()

    @classmethod
    def for_user(cls, user):
        while True:
            id_ = random.randint(0, zeeguu.core.app.config.get("MAX_SESSION"))
            if cls.query.get(id_) is None:
                break
        return cls(user, id_)

    @classmethod
    def find(cls, id: str = None, request=None):

        if id:
            session_id = int(id)
        elif request:
            session_id = int(request.args["session"])
        else:
            return None

        val_from_cache = cls._cache.get(session_id)
        if val_from_cache:
            return val_from_cache

        try:
            val_from_db = cls.query.filter(cls.id == session_id).one()
            cls._cache[session_id] = val_from_db

            return val_from_db
        except NoResultFound:
            return None

    @classmethod
    # to remove ASAP
    def find_for_id(cls, session_id):

        val_from_cache = cls._cache.get(session_id)
        if val_from_cache:
            return val_from_cache

        try:
            val_from_db = cls.query.filter(cls.id == session_id).one()
            cls._cache[session_id] = val_from_db

            return val_from_db
        except NoResultFound:
            return None

    @classmethod
    def find_for_user(cls, user):
        s = (
            cls.query.filter(cls.user == user)
            .filter(cls.id < zeeguu.core.app.config.get("MAX_SESSION"))
            .order_by(desc(cls.last_use))
            .first()
        )
        if not s:
            s = cls.for_user(user)
        return s
