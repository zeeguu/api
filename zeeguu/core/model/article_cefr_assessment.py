"""
CEFR Assessment Model - 1:1 relationship with Article

Stores multiple CEFR assessments per article:
- LLM assessment (from DeepSeek/Anthropic during crawling or simplification)
- ML assessment (from ML classifier or naive FK fallback)
- Teacher assessment (manual override or conflict resolution)

Provides display logic for showing disagreements to teachers.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db


class ArticleCefrAssessment(db.Model):
    """
    1:1 assessment data for articles.

    Stores LLM, ML, and Teacher CEFR assessments in denormalized format
    for fast access without joins.

    Display priority: Teacher > LLM/ML disagreement > LLM > ML
    """

    __tablename__ = "article_cefr_assessment"

    # Primary key is the article ID (enforces 1:1 relationship)
    article_id = Column(Integer, ForeignKey("article.id", ondelete="CASCADE"), primary_key=True)

    # LLM assessment (from DeepSeek/Anthropic)
    llm_cefr_level = Column(Enum("A1", "A2", "B1", "B2", "C1", "C2"))
    llm_method = Column(Enum("llm_assessed_deepseek", "llm_assessed_anthropic"))
    llm_assessed_at = Column(DateTime)

    # ML assessment (from ML classifier or naive FK)
    ml_cefr_level = Column(Enum("A1", "A2", "B1", "B2", "C1", "C2"))
    ml_method = Column(Enum("ml", "ml_word_freq", "naive_fk"))
    ml_assessed_at = Column(DateTime)

    # Teacher assessment (manual override or conflict resolution)
    teacher_cefr_level = Column(Enum("A1", "A2", "B1", "B2", "C1", "C2"))
    teacher_method = Column(Enum("teacher_resolution", "teacher_manual"))
    teacher_assessed_at = Column(DateTime)
    teacher_assessed_by_user_id = Column(Integer, ForeignKey("user.id", ondelete="SET NULL"))

    # Simplification target level (what level we asked LLM to simplify TO)
    # This is different from llm_cefr_level which is what the simplified article actually measures as
    simplification_target_level = Column(Enum("A1", "A2", "B1", "B2", "C1", "C2"))

    # Effective CEFR level - SINGLE SOURCE OF TRUTH for article difficulty
    # Computed from LLM, ML, and Teacher assessments
    # Supports both single levels ("B1") and compound levels for adjacent disagreements ("B1/B2")
    effective_cefr_level = Column(
        Enum(
            "A1", "A2", "B1", "B2", "C1", "C2",
            "A1/A2", "A2/B1", "B1/B2", "B2/C1", "C1/C2"
        )
    )

    # Relationships
    article = relationship("Article", back_populates="cefr_assessment")
    teacher_assessed_by = relationship("User", foreign_keys=[teacher_assessed_by_user_id])

    @classmethod
    def find_or_create(cls, session, article_id, commit=True):
        """
        Get existing assessment record or create new one.

        Args:
            session: SQLAlchemy session
            article_id: ID of the article
            commit: Whether to commit immediately (default True)

        Returns:
            ArticleCefrAssessment instance
        """
        assessment = session.query(cls).filter_by(article_id=article_id).first()
        if not assessment:
            assessment = cls(article_id=article_id)
            session.add(assessment)
            if commit:
                session.commit()
        return assessment

    def set_llm_assessment(self, level, method):
        """
        Store LLM assessment and update effective level.

        Args:
            level: CEFR level (A1-C2)
            method: Assessment method (llm_assessed_deepseek, llm_assessed_anthropic)
        """
        self.llm_cefr_level = level
        self.llm_method = method
        self.llm_assessed_at = datetime.utcnow()
        self.update_effective_cefr_level()

    def set_ml_assessment(self, level, method):
        """
        Store ML assessment and update effective level.

        Args:
            level: CEFR level (A1-C2)
            method: Assessment method (ml, ml_word_freq, naive_fk)
        """
        self.ml_cefr_level = level
        self.ml_method = method
        self.ml_assessed_at = datetime.utcnow()
        self.update_effective_cefr_level()

    def set_teacher_assessment(self, level, method, user_id):
        """
        Store teacher assessment and update effective level.

        Args:
            level: CEFR level (A1-C2)
            method: Assessment method (teacher_resolution, teacher_manual)
            user_id: ID of the teacher who made the assessment
        """
        self.teacher_cefr_level = level
        self.teacher_method = method
        self.teacher_assessed_at = datetime.utcnow()
        self.teacher_assessed_by_user_id = user_id
        self.update_effective_cefr_level()

    def update_effective_cefr_level(self):
        """
        Compute effective CEFR level based on assessment priority.

        This is the SINGLE SOURCE OF TRUTH for article difficulty.

        Priority:
        1. Teacher override (always wins)
        2. LLM and ML synthesis (treating simplification_target_level as LLM assessment):
           - Agreement → Single level: "B1"
           - Adjacent disagreement (1 level apart) → Compound: "B1/B2"
           - Large disagreement (2+ levels apart) → Higher level: "B2" (conservative)
        3. LLM only (or simplification_target_level only)
        4. ML only

        For simplified articles:
        - simplification_target_level represents the LLM's implicit assessment
          (the LLM thought the text it generated was at this level)
        - ml_cefr_level is our measured verification
        - Disagreement between them produces compound levels (e.g., "B1/B2")

        Effective level formats:
        - Single: "B1" - agreement or single assessment
        - Compound: "B1/B2" - adjacent disagreement
        - Conservative: "B2" - large disagreement resolved to higher level
        """
        levels = ["A1", "A2", "B1", "B2", "C1", "C2"]

        # Priority 1: Teacher override always wins
        if self.teacher_cefr_level:
            self.effective_cefr_level = self.teacher_cefr_level
            return

        # Determine effective LLM level (explicit assessment or simplification target)
        effective_llm_level = self.llm_cefr_level or self.simplification_target_level

        # Priority 2: LLM (or simplification target) and ML synthesis
        if effective_llm_level and self.ml_cefr_level:
            if effective_llm_level == self.ml_cefr_level:
                # Agreement
                self.effective_cefr_level = effective_llm_level
            else:
                # Disagreement
                l1, l2 = effective_llm_level, self.ml_cefr_level
                sorted_levels = sorted([l1, l2], key=lambda x: levels.index(x))
                distance = abs(levels.index(l1) - levels.index(l2))

                if distance == 1:
                    # Adjacent levels - use compound
                    self.effective_cefr_level = f"{sorted_levels[0]}/{sorted_levels[1]}"
                else:
                    # Large disagreement (2+ levels) - pick higher (conservative)
                    self.effective_cefr_level = sorted_levels[1]
            return

        # Priority 3: LLM only (or simplification target only)
        if effective_llm_level:
            self.effective_cefr_level = effective_llm_level
            return

        # Priority 4: ML only
        if self.ml_cefr_level:
            self.effective_cefr_level = self.ml_cefr_level
            return

        # No assessments yet
        self.effective_cefr_level = None

    def as_dict(self):
        """
        Return assessment data as dictionary for API responses.

        Returns:
            Dict with llm, ml, teacher assessment data and effective_cefr_level
        """
        return {
            "llm": {
                "level": self.llm_cefr_level,
                "method": self.llm_method,
                "assessed_at": self.llm_assessed_at.isoformat() if self.llm_assessed_at else None
            } if self.llm_cefr_level else None,
            "ml": {
                "level": self.ml_cefr_level,
                "method": self.ml_method,
                "assessed_at": self.ml_assessed_at.isoformat() if self.ml_assessed_at else None
            } if self.ml_cefr_level else None,
            "teacher": {
                "level": self.teacher_cefr_level,
                "method": self.teacher_method,
                "assessed_at": self.teacher_assessed_at.isoformat() if self.teacher_assessed_at else None,
                "assessed_by_user_id": self.teacher_assessed_by_user_id
            } if self.teacher_cefr_level else None,
            "effective_cefr_level": self.effective_cefr_level,
            # Keep display_cefr for backward compatibility
            "display_cefr": self.effective_cefr_level
        }
