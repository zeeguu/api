from datetime import datetime
from random import randint

import zeeguu.core
from sqlalchemy import func

from zeeguu.core.model import db


class UniqueCode(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(4))
    email = db.Column(db.String(255))
    time = db.Column(db.DateTime)

    def __init__(self, email):
        self.code = randint(100, 999)
        self.email = email
        self.time = datetime.now()

    def __str__(self):
        return str(self.code)

    @classmethod
    def last_code(cls, email):
        return (
            cls.query.filter(cls.email == email).order_by(cls.time.desc()).first()
        ).code

    @classmethod
    def all_codes_for(cls, email):
        return (cls.query.filter(func.lower(cls.email) == email.lower())).all()
