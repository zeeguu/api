import json
import logging

from sqlalchemy import Column, Integer, UnicodeText, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError, OperationalError
from datetime import datetime, timedelta
from zeeguu.core.model.db import db

log = logging.getLogger(__name__)


class CaptionTokenizationCache(db.Model):
    """
    Caches the Stanza-based tokenized text for video captions to avoid
    re-running tokenization on every GET /user_video. Mirrors the
    ArticleTokenizationCache pattern.

    Captions are immutable once a video is ingested, so cache entries do not
    need to be invalidated -- only populated on first read.
    """

    __tablename__ = "caption_tokenization_cache"

    caption_id = Column(
        Integer, ForeignKey("caption.id", ondelete="CASCADE"), primary_key=True
    )
    tokenized_text = Column(UnicodeText)
    created_at = Column(DateTime, default=datetime.now)

    @classmethod
    def find_or_create(cls, session, caption_id):
        cache = session.query(cls).filter_by(caption_id=caption_id).first()
        if cache:
            return cache

        cache = cls(caption_id=caption_id)
        session.add(cache)
        try:
            session.flush()
        except IntegrityError:
            # Another request beat us to the insert -- fetch and return that one.
            session.rollback()
            cache = session.query(cls).filter_by(caption_id=caption_id).first()
        except OperationalError as e:
            log.warning(
                f"[CACHE] OperationalError during cache creation for caption "
                f"{caption_id}: {e}"
            )
            session.rollback()
            cache = session.query(cls).filter_by(caption_id=caption_id).first()
        return cache

    @classmethod
    def get_many(cls, session, caption_ids):
        """One query for many caption ids. Returns {caption_id: tokenized_text_json_string}."""
        if not caption_ids:
            return {}
        rows = (
            session.query(cls.caption_id, cls.tokenized_text)
            .filter(cls.caption_id.in_(caption_ids))
            .all()
        )
        return {cid: tok for (cid, tok) in rows}

    @classmethod
    def delete_older_than(cls, session, days=30):
        cutoff = datetime.now() - timedelta(days=days)
        deleted = session.query(cls).filter(cls.created_at < cutoff).delete()
        session.commit()
        log.info(
            f"[CACHE-CLEANUP] Deleted {deleted} caption-cache entries older than {days} days"
        )
        return deleted
