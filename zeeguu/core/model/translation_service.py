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

    # Never accepted from a client: they would claim our own provenance
    INTERNAL = (MANUAL, CHOSEN_ALTERNATIVE, LEARNING_CARD, VALIDATOR)

    @classmethod
    def find_or_create(cls, session, name):
        """
        For names from our own code and from the translate endpoint's engines;
        a name from a client goes through known() instead.

        Never flushes the caller's pending work: callers are mid-way through
        reassigning a bookmark (update_bookmark_full, the validator's fix),
        and a flush there would write that half-done state, which the
        preferred-bookmark write check (user_word.py) can reject. So the
        lookups skip autoflush and a new row is committed in a session of its
        own; a stray service row is harmless if the caller then rolls back.
        """
        name = name.strip()[:50]
        with session.no_autoflush:
            found = session.query(cls).filter_by(name=name).first()
        if found:
            return found

        from sqlalchemy.orm import sessionmaker

        own = sessionmaker(bind=session.get_bind())()
        try:
            own.add(cls(name))
            own.commit()
        except IntegrityError:
            own.rollback()  # another request created it first
        finally:
            own.close()
        # A locking read: a plain SELECT would reuse the caller's REPEATABLE
        # READ snapshot from the lookup above, which predates the new row.
        with session.no_autoflush:
            return session.query(cls).filter_by(name=name).with_for_update(read=True).one()

    @classmethod
    def known(cls, name):
        """The existing engine with this name, or None; never creates one and
        never returns one of our INTERNAL names. For names from a client."""
        if not isinstance(name, str) or not name.strip():
            return None
        name = name.strip()[:50]
        if name in cls.INTERNAL:
            return None
        return cls.query.filter_by(name=name).first()
