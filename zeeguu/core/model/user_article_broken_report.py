"""
Track user reports of broken articles.

When multiple users report an article as broken, it gets automatically
marked with the USER_REPORTED code.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
import sqlalchemy

from zeeguu.core.model.db import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.user import User


# Threshold: mark as broken when this many regular users report it
USER_REPORT_THRESHOLD = 2
# Teachers (trusted users) can mark as broken immediately
TEACHER_CAN_MARK_IMMEDIATELY = True


class UserArticleBrokenReport(db.Model):
    """
    Tracks when users report articles as broken.

    When USER_REPORT_THRESHOLD users report the same article,
    it's automatically marked as broken with USER_REPORTED code.
    """

    __tablename__ = "user_article_broken_report"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="user_article_unique"),
        {"mysql_collate": "utf8_bin"},
    )

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    user = relationship(User)

    article_id = Column(Integer, ForeignKey(Article.id), nullable=False)
    article = relationship(Article)

    report_time = Column(DateTime, nullable=False)
    reason = Column(String(255))  # Optional: user can provide reason

    def __init__(self, user: User, article: Article, reason: str = None):
        self.user = user
        self.article = article
        self.report_time = datetime.now()
        self.reason = reason

    def __str__(self):
        return (
            f"UserArticleBrokenReport(user={self.user_id}, article={self.article_id})"
        )

    __repr__ = __str__

    @classmethod
    def create(cls, session, user: User, article: Article, reason: str = None):
        """
        Create a new user report for a broken article.

        If threshold is reached (2 users) OR user is a teacher, automatically marks article as broken.
        Returns (report, was_marked_broken)
        """
        from zeeguu.core.model.article_broken_code_map import (
            ArticleBrokenMap,
            LowQualityTypes,
        )

        # Check if user already reported this article
        existing = cls.find(session, user, article)
        if existing:
            return existing, False

        # Create new report
        report = cls(user, article, reason)
        session.add(report)

        # Count total reports for this article
        total_reports = cls.count_for_article(session, article)

        # Check if user is a teacher (trusted user)
        is_teacher = user.isTeacher()

        # Mark as broken if:
        # 1. Threshold reached (2+ regular users reported), OR
        # 2. Reporter is a teacher (immediate trust)
        was_marked = False
        should_mark = (total_reports >= USER_REPORT_THRESHOLD) or (
            TEACHER_CAN_MARK_IMMEDIATELY and is_teacher
        )

        if should_mark:
            # Check if not already marked with USER_REPORTED
            existing_mark = ArticleBrokenMap.query.filter(
                ArticleBrokenMap.article_id == article.id,
                ArticleBrokenMap.broken_code == LowQualityTypes.USER_REPORTED,
            ).first()

            if not existing_mark:
                article.set_as_broken(session, LowQualityTypes.USER_REPORTED)
                was_marked = True

        session.commit()
        return report, was_marked

    @classmethod
    def find(cls, session, user: User, article: Article):
        """Find existing report by user for article."""
        try:
            return cls.query.filter(
                cls.user_id == user.id, cls.article_id == article.id
            ).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def count_for_article(cls, session, article: Article) -> int:
        """Count how many users reported this article."""
        return cls.query.filter(cls.article_id == article.id).count()

    @classmethod
    def all_for_article(cls, session, article: Article):
        """Get all reports for an article."""
        return cls.query.filter(cls.article_id == article.id).all()

    @classmethod
    def all_for_user(cls, session, user: User):
        """Get all reports by a user."""
        return cls.query.filter(cls.user_id == user.id).all()

    @classmethod
    def recent_reports(cls, session, days: int = 7):
        """Get reports from last N days."""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        return cls.query.filter(cls.report_time >= cutoff).all()
