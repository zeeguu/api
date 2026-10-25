from datetime import datetime
from enum import Enum

from zeeguu.core.model.db import db


class ValidationAction(Enum):
    VALID = "valid"
    FIXED = "fixed"
    INVALID = "invalid"


class ValidationLog(db.Model):
    """
    Tracks validation results for analysis.

    Helps understand what kinds of translations are being fixed,
    common error patterns, and validation effectiveness.
    """

    __tablename__ = "validation_log"

    id = db.Column(db.Integer, primary_key=True)

    meaning_id = db.Column(
        db.Integer,
        db.ForeignKey("meaning.id"),
        nullable=False
    )
    meaning = db.relationship(
        "Meaning",
        foreign_keys=[meaning_id],
        backref="validation_logs"
    )

    new_meaning_id = db.Column(
        db.Integer,
        db.ForeignKey("meaning.id"),
        nullable=True
    )
    new_meaning = db.relationship(
        "Meaning",
        foreign_keys=[new_meaning_id]
    )

    user_word_id = db.Column(db.Integer, nullable=True)

    # The column holds the values ('fixed'), as the migration created it, not
    # the names ('FIXED') SQLAlchemy maps by default. Writes passed either way
    # (MySQL compares enum values case-insensitively); reading a row back
    # raised LookupError until 25 Oct 2026.
    action = db.Column(
        db.Enum(ValidationAction, values_callable=lambda actions: [a.value for a in actions]),
        nullable=False
    )

    reason = db.Column(db.Text, nullable=True)
    context = db.Column(db.Text, nullable=True)

    # Who produced the translation this verdict judged. Kept here because a FIX
    # moves the bookmark to the corrected pair, and with it the bookmark's own
    # translation_service; this is how a wrong pair is traced to its engine.
    translation_service_id = db.Column(
        db.SmallInteger,
        db.ForeignKey("translation_service.id", name="validation_log_translation_service_fk"),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.now,
        nullable=False
    )

    def __init__(
        self,
        meaning,
        action,
        new_meaning=None,
        user_word_id=None,
        reason=None,
        context=None,
        translation_service_id=None,
    ):
        self.meaning = meaning
        self.action = action
        self.new_meaning = new_meaning
        self.user_word_id = user_word_id
        self.reason = reason
        self.context = context
        self.translation_service_id = translation_service_id

    @classmethod
    def log_valid(cls, db_session, meaning, user_word_id=None, context=None, translation_service_id=None):
        """Log a valid translation."""
        log_entry = cls(
            meaning=meaning,
            action=ValidationAction.VALID,
            user_word_id=user_word_id,
            context=context,
            translation_service_id=translation_service_id,
        )
        db_session.add(log_entry)
        return log_entry

    @classmethod
    def log_fixed(cls, db_session, old_meaning, new_meaning, user_word_id=None, reason=None, context=None,
                  translation_service_id=None):
        """Log a fixed translation."""
        log_entry = cls(
            meaning=old_meaning,
            action=ValidationAction.FIXED,
            new_meaning=new_meaning,
            user_word_id=user_word_id,
            reason=reason,
            context=context,
            translation_service_id=translation_service_id,
        )
        db_session.add(log_entry)
        return log_entry

    @classmethod
    def log_invalid(cls, db_session, meaning, user_word_id=None, reason=None, context=None,
                    translation_service_id=None):
        """Log an invalid translation that couldn't be fixed."""
        log_entry = cls(
            meaning=meaning,
            action=ValidationAction.INVALID,
            user_word_id=user_word_id,
            reason=reason,
            context=context,
            translation_service_id=translation_service_id,
        )
        db_session.add(log_entry)
        return log_entry

    def __repr__(self):
        return f"<ValidationLog {self.id}: {self.action.value} for meaning {self.meaning_id}>"
