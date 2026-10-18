"""
Which translator produced a translation: the translate endpoint's winning
service ("DeepL", "Microsoft - alignment", "LLM", ...), the learner's own
("MANUAL"), an alternative the learner picked, or the translation validator.

Rows are created on first use rather than enumerated, so a new engine or a
renamed source needs no migration; bookmark and validation_log store the id.
"""

from sqlalchemy import Column, Integer, SmallInteger, String
from sqlalchemy.exc import IntegrityError

from zeeguu.core.model.db import db


class TranslationService(db.Model):
    __tablename__ = "translation_service"
    __table_args__ = {"mysql_collate": "utf8mb4_unicode_ci"}

    # Sources written by our own code rather than returned by an engine
    MANUAL = "MANUAL"  # typed by the learner
    CHOSEN_ALTERNATIVE = "Chosen alternative"  # picked in the reader; client did not say whose
    LEARNING_CARD = "Learning card (LLM)"  # word added via the learning card generator
    VALIDATOR = "Translation validator"  # replaced by UserWordValidationService

    # SMALLINT in MySQL, as the migration creates it. SQLite (the tests) only
    # autoincrements INTEGER PRIMARY KEY, so a SMALLINT key there gets no id.
    id = Column(SmallInteger().with_variant(Integer, "sqlite"), primary_key=True)
    name = Column(String(50), nullable=False, unique=True)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<TranslationService {self.name}>"

    @classmethod
    def find_or_create(cls, session, name):
        name = name[:50]
        found = cls.query.filter_by(name=name).first()
        if found:
            return found
        # Under a savepoint, so losing the race to another request undoes this
        # insert only, not the caller's pending bookmark.
        try:
            with session.begin_nested():
                found = cls(name)
                session.add(found)
        except IntegrityError:
            # Another request created it first; anything else is a real error.
            # A locking read: a plain SELECT would reuse this transaction's
            # REPEATABLE READ snapshot from the lookup above, which predates
            # the other request's row.
            found = cls.query.filter_by(name=name).with_for_update(read=True).first()
            if found is None:
                raise
        return found

    @classmethod
    def known(cls, name):
        """The existing service with this name, or None; never creates one.
        For names that come from a client rather than from our own code."""
        if not isinstance(name, str) or not name.strip():
            return None
        return cls.query.filter_by(name=name.strip()[:50]).first()
