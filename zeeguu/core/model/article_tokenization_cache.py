import json
import logging

from sqlalchemy import Column, Integer, UnicodeText, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError, OperationalError
from datetime import datetime, timedelta
from zeeguu.core.model.db import db

log = logging.getLogger(__name__)


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

        Flushes immediately to avoid deadlocks from autoflush during
        subsequent queries in the same request. Handles race conditions
        where multiple concurrent requests try to create the same cache.
        """
        cache = session.query(cls).filter_by(article_id=article.id).first()
        if cache:
            return cache

        # Try to create and flush immediately
        cache = cls(article_id=article.id)
        session.add(cache)
        try:
            session.flush()
        except IntegrityError:
            # Another request created it first - rollback and fetch
            session.rollback()
            cache = session.query(cls).filter_by(article_id=article.id).first()
        except OperationalError as e:
            # Lock wait timeout or other DB operational error - rollback to clean session state
            # This prevents PendingRollbackError in subsequent operations
            log.warning(f"[CACHE] OperationalError during cache creation for article {article.id}: {e}")
            session.rollback()
            # Try to fetch existing cache (another process may have created it)
            cache = session.query(cls).filter_by(article_id=article.id).first()

        return cache

    @classmethod
    def get_for_article(cls, session, article_id):
        """Get cache for article, returns None if not found"""
        return session.query(cls).filter_by(article_id=article_id).first()

    @classmethod
    def ensure_populated(cls, session, article):
        """
        Ensure cache exists and is populated with tokenized summary and title.

        This separates the write concern (populating cache) from the read concern
        (using cached data), allowing callers to batch all writes before reads.
        """
        from zeeguu.core.mwe import tokenize_for_reading

        cache = cls.find_or_create(session, article)
        modified = False

        # Populate summary if needed
        if article.summary and not cache.tokenized_summary:
            tokenized = tokenize_for_reading(article.summary, article.language, mode="stanza")
            cache.tokenized_summary = json.dumps(tokenized)
            modified = True
            log.info(f"[CACHE] Article {article.id} - Tokenized and cached summary with MWE")

        # Populate title if needed
        if not cache.tokenized_title:
            tokenized = tokenize_for_reading(article.title, article.language, mode="stanza")
            cache.tokenized_title = json.dumps(tokenized)
            modified = True
            log.info(f"[CACHE] Article {article.id} - Tokenized and cached title with MWE")

        return cache, modified

    @classmethod
    def delete_older_than(cls, session, days=7):
        """Delete cache entries older than N days. Returns count of deleted rows."""
        cutoff = datetime.now() - timedelta(days=days)
        deleted = session.query(cls).filter(cls.created_at < cutoff).delete()
        session.commit()
        log.info(f"[CACHE-CLEANUP] Deleted {deleted} cache entries older than {days} days")
        return deleted
