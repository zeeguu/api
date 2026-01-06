import hashlib
from datetime import datetime

from zeeguu.core.model import User, Article
from zeeguu.core.model.db import db


class UserMweOverride(db.Model):
    """
    Stores user overrides for incorrect MWE (Multi-Word Expression) groupings.
    When a user "ungroups" an MWE, we store it here so future article loads
    skip that MWE for this user.

    Uses sentence_hash (SHA256 of sentence text) instead of sentence_i.
    This survives article re-ordering and naturally invalidates if sentence is edited.

    Stores mwe_expression (the actual words like "har lavet") instead of mwe_group_id.
    This survives re-tokenization where mwe_group_id might change.
    """

    __table_args__ = dict(mysql_collate="utf8_bin")
    __tablename__ = "user_mwe_override"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship(User)

    article_id = db.Column(db.Integer, db.ForeignKey(Article.id), nullable=False)
    article = db.relationship(Article)

    sentence_hash = db.Column(db.String(64), nullable=False)
    mwe_expression = db.Column(db.String(255), nullable=False)
    disabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __init__(self, user_id, article_id, sentence_hash, mwe_expression, disabled=True):
        self.user_id = user_id
        self.article_id = article_id
        self.sentence_hash = sentence_hash
        self.mwe_expression = mwe_expression.lower().strip()
        self.disabled = disabled
        self.created_at = datetime.now()

    @staticmethod
    def compute_sentence_hash(sentence_text):
        """Compute SHA256 hash of normalized sentence text."""
        normalized = sentence_text.strip().lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    @staticmethod
    def normalize_mwe(mwe_expression):
        """Normalize MWE expression for matching."""
        return mwe_expression.lower().strip()

    @classmethod
    def find_or_create(cls, session, user_id, article_id, sentence_hash, mwe_expression):
        """Find existing override or create a new one."""
        normalized_mwe = cls.normalize_mwe(mwe_expression)
        existing = cls.query.filter_by(
            user_id=user_id,
            article_id=article_id,
            sentence_hash=sentence_hash,
            mwe_expression=normalized_mwe
        ).first()

        if existing:
            existing.disabled = True
            return existing

        override = cls(user_id, article_id, sentence_hash, mwe_expression)
        session.add(override)
        return override

    @classmethod
    def get_disabled_mwes_for_user_article(cls, user_id, article_id):
        """Get dict mapping sentence_hash -> list of disabled mwe_expressions."""
        overrides = cls.query.filter_by(
            user_id=user_id,
            article_id=article_id,
            disabled=True
        ).all()

        result = {}
        for o in overrides:
            if o.sentence_hash not in result:
                result[o.sentence_hash] = []
            result[o.sentence_hash].append(o.mwe_expression)
        return result
