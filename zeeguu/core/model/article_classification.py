from sqlalchemy import PrimaryKeyConstraint, DateTime
from sqlalchemy.orm import relationship
from zeeguu.core.model.article import Article
from datetime import datetime

import sqlalchemy

from zeeguu.core.model.db import db


class ClassificationType:
    """Content classification types for articles."""
    DISTURBING = "DISTURBING"      # Violence, death, tragedy
    NEGATIVE_NEWS = "NEGATIVE_NEWS"  # Pessimistic news, economic downturns, depressing content


class DetectionMethod:
    """How the classification was detected."""
    KEYWORD = "KEYWORD"  # Pattern/keyword matching
    LLM = "LLM"          # Detected by LLM during processing


class ArticleClassification(db.Model):
    """
    Tracks content classifications for articles.

    Unlike ArticleBrokenMap (for broken/low-quality content), this tracks
    valid content that users may want to filter based on preferences.

    Examples: disturbing news (violence/death), negative news (economic/pessimistic)
    """

    __tablename__ = "article_classification"

    article_id = db.Column(db.Integer, db.ForeignKey(Article.id, ondelete="CASCADE"))
    article = relationship(Article)

    classification_type = db.Column(
        db.Enum("DISTURBING", "NEGATIVE_NEWS"),
        nullable=False
    )
    detection_method = db.Column(
        db.Enum("KEYWORD", "LLM"),
        nullable=False
    )
    detected_at = db.Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint(article_id, classification_type),
        {"mysql_collate": "utf8_bin"},
    )

    def __init__(self, article: Article, classification_type: str, detection_method: str):
        self.article = article
        self.classification_type = classification_type
        self.detection_method = detection_method

    def __str__(self):
        return f"ArticleClassification({self.article_id}, {self.classification_type}, {self.detection_method})"

    __repr__ = __str__

    @classmethod
    def find_or_create(cls, session, article: Article, classification_type: str, detection_method: str):
        """Find or create a classification for an article."""
        try:
            return (
                cls.query.filter(cls.article == article)
                .filter(cls.classification_type == classification_type)
                .one()
            )
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(article, classification_type, detection_method)
            session.add(new)
            session.commit()
            return new

    @classmethod
    def get_classifications(cls, article: Article) -> dict:
        """
        Get all classifications for an article as a dict.

        Returns:
            dict: {classification_type: detection_method}
            Example: {"DISTURBING": "KEYWORD", "NEGATIVE_NEWS": "LLM"}
        """
        classifications = cls.query.filter_by(article_id=article.id).all()
        return {c.classification_type: c.detection_method for c in classifications}

    @classmethod
    def has_classification(cls, article: Article, classification_type: str) -> bool:
        """Check if article has a specific classification."""
        return (
            cls.query.filter_by(article_id=article.id, classification_type=classification_type)
            .first() is not None
        )
