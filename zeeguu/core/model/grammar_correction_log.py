"""
Tracks grammar/spelling corrections made to simplified articles.

This allows us to:
1. See how many errors are being fixed
2. Identify patterns in errors
3. Compare error rates between different simplification models
4. Evaluate if the correction pass is worth the cost
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from zeeguu.core.model.db import db


class CorrectionFieldType(Enum):
    TITLE = "title"
    CONTENT = "content"
    SUMMARY = "summary"


class GrammarCorrectionLog(db.Model):
    """
    Log of grammar/spelling corrections made to simplified articles.
    """

    __tablename__ = "grammar_correction_log"
    __table_args__ = {"mysql_collate": "utf8mb4_unicode_ci"}

    id = Column(Integer, primary_key=True)

    # Which article was corrected
    article_id = Column(Integer, ForeignKey("article.id"), nullable=False, index=True)
    article = relationship("Article")

    # What field was corrected
    field_type = Column(SQLEnum(CorrectionFieldType), nullable=False)

    # The actual correction
    original_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=False)

    # Language for easier querying
    language_code = Column(String(10), nullable=False, index=True)

    # Which model did the simplification (to correlate errors with simplifiers)
    simplification_model = Column(String(100), nullable=True)

    # Which model did the correction
    correction_model = Column(String(100), nullable=False)

    # When
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __init__(
        self,
        article_id,
        field_type,
        original_text,
        corrected_text,
        language_code,
        correction_model,
        simplification_model=None,
    ):
        self.article_id = article_id
        self.field_type = field_type
        self.original_text = original_text
        self.corrected_text = corrected_text
        self.language_code = language_code
        self.correction_model = correction_model
        self.simplification_model = simplification_model

    def __repr__(self):
        return f"<GrammarCorrectionLog article={self.article_id} field={self.field_type}>"

    @classmethod
    def log_correction(
        cls,
        session,
        article_id,
        field_type,
        original_text,
        corrected_text,
        language_code,
        correction_model,
        simplification_model=None,
    ):
        """
        Log a grammar correction if there was actually a change.

        Returns:
            GrammarCorrectionLog if correction was logged, None if texts were identical
        """
        # Only log if there was an actual change
        if original_text == corrected_text:
            return None

        log_entry = cls(
            article_id=article_id,
            field_type=field_type,
            original_text=original_text,
            corrected_text=corrected_text,
            language_code=language_code,
            correction_model=correction_model,
            simplification_model=simplification_model,
        )
        session.add(log_entry)
        return log_entry

    @classmethod
    def get_corrections_for_article(cls, article_id):
        """Get all corrections made to an article."""
        return cls.query.filter_by(article_id=article_id).all()

    @classmethod
    def get_corrections_by_language(cls, language_code, limit=100):
        """Get recent corrections for a language."""
        return (
            cls.query.filter_by(language_code=language_code)
            .order_by(cls.created_at.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def get_correction_stats_by_simplifier(cls, language_code=None):
        """
        Get correction counts grouped by simplification model.
        Useful for comparing error rates between DeepSeek and Anthropic.

        Returns:
            List of (simplification_model, correction_count) tuples
        """
        from sqlalchemy import func

        query = db.session.query(
            cls.simplification_model,
            func.count(cls.id).label('correction_count')
        ).group_by(cls.simplification_model)

        if language_code:
            query = query.filter(cls.language_code == language_code)

        return query.all()

    @classmethod
    def get_correction_stats_by_field(cls, language_code=None):
        """
        Get correction counts grouped by field type.

        Returns:
            List of (field_type, correction_count) tuples
        """
        from sqlalchemy import func

        query = db.session.query(
            cls.field_type,
            func.count(cls.id).label('correction_count')
        ).group_by(cls.field_type)

        if language_code:
            query = query.filter(cls.language_code == language_code)

        return query.all()
