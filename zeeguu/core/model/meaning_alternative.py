from datetime import datetime

from sqlalchemy.dialects import mysql

from zeeguu.core.model.db import db


class MeaningAlternative(db.Model):
    """
    A word a learner may type for a meaning, judged once by an LLM: another
    word in a cloze exercise ('tænker' for 'synes'), or another translation of
    it ('consult' for 'look up'); language_id tells which. See the migrations
    26-10-14-b--add_meaning_alternative.sql for the key (meaning, not phrase),
    the sentence hash on context-specific verdicts, and user_id on verdicts
    that are not shared, and 26-10-14-c--meaning_alternative_language.sql.
    """

    __tablename__ = "meaning_alternative"
    __table_args__ = (
        db.UniqueConstraint(
            "meaning_id",
            "language_id",
            "alternative",
            "context_hash",
            "user_id",
            name="uq_meaning_alternative_language",
        ),
    )

    SYNONYM = "SYNONYM"
    NEAR_SYNONYM_NOT_IDIOMATIC = "NEAR_SYNONYM_NOT_IDIOMATIC"
    NOT_SYNONYM = "NOT_SYNONYM"
    RELATIONS = (SYNONYM, NEAR_SYNONYM_NOT_IDIOMATIC, NOT_SYNONYM)

    GENERAL = ""  # context_hash of a verdict that holds in any sentence

    id = db.Column(db.Integer, primary_key=True)
    meaning_id = db.Column(db.Integer, db.ForeignKey("meaning.id", ondelete="CASCADE"), nullable=False)
    # The language of the typed answer: the meaning's origin language for a
    # cloze, its translation language for a typed translation.
    language_id = db.Column(db.Integer, db.ForeignKey("language.id"), nullable=False)
    # Binary collation: 'esta' is not 'está', 'pa' is not 'på'.
    alternative = db.Column(
        db.String(255).with_variant(mysql.VARCHAR(255, collation="utf8mb4_bin"), "mysql"),
        nullable=False,
    )
    context_hash = db.Column(db.CHAR(64), nullable=False, default=GENERAL)
    # NULL: shared by all learners. Set: only for this learner (an accepting
    # verdict nobody else has corroborated, see cloze_alternatives).
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"))
    relation = db.Column(db.Enum(*RELATIONS), nullable=False)
    explanation = db.Column(db.Text)
    ai_generator_id = db.Column(db.Integer, db.ForeignKey("ai_generator.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=datetime.now)

    meaning = db.relationship("Meaning")
    language = db.relationship("Language")
    ai_generator = db.relationship("AIGenerator")

    @classmethod
    def lookup(cls, meaning_id, language_id, alternative, context_hash, user_id):
        """The stored verdict that applies here, the most specific first: one
        made for this very sentence beats a general one."""
        rows = cls.query.filter(
            cls.meaning_id == meaning_id,
            cls.language_id == language_id,
            cls.alternative == alternative,
            cls.context_hash.in_([cls.GENERAL, context_hash]),
            db.or_(cls.user_id.is_(None), cls.user_id == user_id),
        ).all()
        rows.sort(key=lambda r: r.context_hash == cls.GENERAL)
        return rows[0] if rows else None
