from datetime import datetime, timedelta
import secrets

import zeeguu.core
from sqlalchemy import func

from zeeguu.core.model.db import db

# Password reset codes expire after 15 minutes
CODE_EXPIRATION_MINUTES = 15


class UniqueCode(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64))  # Increased from 4 to 64 for secure tokens
    email = db.Column(db.String(255))
    time = db.Column(db.DateTime)

    def __init__(self, email):
        # Generate cryptographically secure 32-byte token (64 hex chars)
        self.code = secrets.token_hex(32)
        self.email = email
        self.time = datetime.now()

    def is_expired(self):
        """Check if the code has expired"""
        expiration_time = self.time + timedelta(minutes=CODE_EXPIRATION_MINUTES)
        return datetime.now() > expiration_time

    def __str__(self):
        return str(self.code)

    @classmethod
    def last_code(cls, email):
        code_obj = cls.find_last_code(email)
        return code_obj.code if code_obj else None

    @classmethod
    def find_last_code(cls, email):
        """Return the last code object for the given email, or None if not found"""
        return cls.query.filter(cls.email == email).order_by(cls.time.desc()).first()

    @classmethod
    def all_codes_for(cls, email):
        return (cls.query.filter(func.lower(cls.email) == email.lower())).all()
