from datetime import datetime

from zeeguu.core.model.db import db


class MeaningAlternative(db.Model):
    """
    A word a learner may type for a meaning in a cloze exercise, judged once by
    an LLM and shared by all learners. See the migration
    26-10-14-b--add_meaning_alternative.sql for why it is keyed on the meaning
    and why a context-specific verdict carries the sentence's hash.
    """

    __tablename__ = "meaning_alternative"
    __table_args__ = (
        db.UniqueConstraint("meaning_id", "alternative", "context_hash", name="uq_meaning_alternative"),
    )

    SYNONYM = "SYNONYM"
    NEAR_SYNONYM_NOT_IDIOMATIC = "NEAR_SYNONYM_NOT_IDIOMATIC"
    NOT_SYNONYM = "NOT_SYNONYM"
    RELATIONS = (SYNONYM, NEAR_SYNONYM_NOT_IDIOMATIC, NOT_SYNONYM)

    GENERAL = ""  # context_hash of a verdict that holds in any sentence

    id = db.Column(db.Integer, primary_key=True)
    meaning_id = db.Column(db.Integer, db.ForeignKey("meaning.id", ondelete="CASCADE"), nullable=False)
    alternative = db.Column(db.String(255), nullable=False)
    context_hash = db.Column(db.String(64), nullable=False, default=GENERAL)
    relation = db.Column(db.Enum(*RELATIONS), nullable=False)
    explanation = db.Column(db.Text)
    ai_generator_id = db.Column(db.Integer, db.ForeignKey("ai_generator.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=datetime.now)

    meaning = db.relationship("Meaning")
    ai_generator = db.relationship("AIGenerator")

    @classmethod
    def lookup(cls, meaning_id, alternative, context_hash):
        """The stored verdict for this sentence: a general one if there is one,
        else one made for exactly this sentence."""
        rows = cls.query.filter(
            cls.meaning_id == meaning_id,
            cls.alternative == alternative,
            cls.context_hash.in_([cls.GENERAL, context_hash]),
        ).all()
        rows.sort(key=lambda r: r.context_hash != cls.GENERAL)
        return rows[0] if rows else None
