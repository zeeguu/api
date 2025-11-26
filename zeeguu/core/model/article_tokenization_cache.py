from sqlalchemy import Column, Integer, UnicodeText, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError
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
        """
        Find existing cache or create new empty cache for article.

        Handles race conditions where the same article might be processed
        multiple times in the same request (e.g., duplicates in search results)
        by checking if we already have a pending cache object in the session.
        """
        # First check if we already have this cache in the session's identity map
        # This handles the case where the same article appears multiple times
        # in the same request (e.g., duplicates in search/recommendations)
        for obj in session.new:
            if isinstance(obj, cls) and obj.article_id == article.id:
                return obj

        cache = session.query(cls).filter_by(article_id=article.id).first()
        if not cache:
            cache = cls(article_id=article.id)
            session.add(cache)
        return cache

    @classmethod
    def get_for_article(cls, session, article_id):
        """Get cache for article, returns None if not found"""
        return session.query(cls).filter_by(article_id=article_id).first()
