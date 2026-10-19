from datetime import datetime, timedelta
import secrets

import zeeguu.core
from sqlalchemy import func

from zeeguu.core.model.db import db

# Password reset codes expire after 15 minutes
CODE_EXPIRATION_MINUTES = 15


class UniqueCode(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    # What a code was issued for. Each endpoint that redeems codes asks for
    # its own purpose, so a code only ever works where it was meant to.
    RESET = "reset"  # mailed by /send_code, redeemed by /reset_password
    VERIFY = "verify"  # email confirmation: /confirm_email, /complete_account_upgrade
    CHANGE_EMAIL = "change_email"  # /request_email_change, /confirm_email_change

    # Submissions a code survives. Four digits are only a small space, so the
    # code itself has to stop answering after a few tries; the rate limiter
    # helps, but its counters are per worker and start over on every restart.
    MAX_ATTEMPTS = 5

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6))  # 4-digit numeric code
    email = db.Column(db.String(255))
    time = db.Column(db.DateTime)
    purpose = db.Column(db.String(16))
    attempts = db.Column(db.Integer, nullable=False, default=0)

    def __init__(self, email, purpose):
        if purpose not in (self.RESET, self.VERIFY, self.CHANGE_EMAIL):
            raise ValueError(f"unknown code purpose {purpose!r}")
        # 4-digit numeric code — easy to type on mobile. 10,000 possibilities
        # are enough only together with the 15-min expiry and MAX_ATTEMPTS.
        self.code = str(secrets.randbelow(10000)).zfill(4)
        self.email = email
        self.purpose = purpose
        self.attempts = 0
        self.time = datetime.now()

    def is_expired(self):
        """Check if the code has expired"""
        expiration_time = self.time + timedelta(minutes=CODE_EXPIRATION_MINUTES)
        return datetime.now() > expiration_time

    def claim_attempt(self, session):
        """
        Count one submission against this code, and say whether it may still
        be checked.

        The count goes up *before* the submitted value is compared, in a single
        conditional UPDATE, so that requests arriving in parallel cannot all
        read the same count and all get checked. A correct submission deletes
        the code, so counting it as an attempt costs nothing.
        """
        cls = type(self)
        claimed = (
            session.query(cls)
            .filter(cls.id == self.id, cls.attempts < cls.MAX_ATTEMPTS)
            .update({cls.attempts: cls.attempts + 1}, synchronize_session=False)
        )
        session.commit()
        return claimed == 1

    def __str__(self):
        return str(self.code)

    @classmethod
    def last_code(cls, email, purpose):
        code_obj = cls.find_last_code(email, purpose)
        return code_obj.code if code_obj else None

    @classmethod
    def find_last_code(cls, email, purpose):
        """Return the last code issued for this email and purpose, or None"""
        return (
            cls.query.filter(cls.email == email, cls.purpose == purpose)
            .order_by(cls.time.desc(), cls.id.desc())
            .first()
        )

    @classmethod
    def all_codes_for(cls, email):
        return (cls.query.filter(func.lower(cls.email) == email.lower())).all()
