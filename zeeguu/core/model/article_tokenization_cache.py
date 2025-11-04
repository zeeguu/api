from sqlalchemy import Column, Integer, UnicodeText, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from zeeguu.core.model.db import db


class ArticleTokenizationCache(db.Model):
    """
    Caches tokenized summary and title for articles to avoid expensive CPU-bound
    Stanza tokenization on every request.

    1-to-1 relationship with Article - keeps article table lean while providing
    fast lookups for cached tokenization.
    """
    __tablename__ = "article_tokenization_cache"

    article_id = Column(Integer, ForeignKey("article.id", ondelete="CASCADE"), primary_key=True)
    tokenized_summary = Column(UnicodeText)
    tokenized_title = Column(UnicodeText)
    created_at = Column(DateTime, default=datetime.now)

    article = relationship("Article", back_populates="tokenization_cache")

    @classmethod
    def find_or_create(cls, session, article):
        """Find existing cache or create new empty cache for article"""
        cache = session.query(cls).filter_by(article_id=article.id).first()
        if not cache:
            cache = cls(article_id=article.id)
            session.add(cache)
        return cache

    @classmethod
    def get_for_article(cls, session, article_id):
        """Get cache for article, returns None if not found"""
        return session.query(cls).filter_by(article_id=article_id).first()
