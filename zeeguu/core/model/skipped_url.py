from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model.article import UnsignedBigInteger
from zeeguu.core.model.db import db
from zeeguu.core.model.feed import Feed
from zeeguu.core.model.url import Url


class SkippedUrl(db.Model):
    """
    A feed item the crawler rejected without saving an article, so that the
    next crawl does not download it and ask the LLM about it again.

    Without it an over-quota paywall, which leaves no article behind, was sent
    to the LLM again every hour while it stayed in the feed: on 19 Oct 2026, 115
    LLM calls for 23 URLs.

    Keyed by url; the simhash also catches the same text republished under
    a new url (outlets rename the slug when they edit the headline).
    """

    __tablename__ = "skipped_url"

    id = Column(Integer, primary_key=True)

    url_id = Column(Integer, ForeignKey(Url.id), unique=True, nullable=False)
    url = relationship(Url)

    feed_id = Column(Integer, ForeignKey(Feed.id))
    content_simhash = Column(UnsignedBigInteger)
    reason = Column(String(42), nullable=False)
    skipped_at = Column(DateTime, nullable=False)

    PAYWALL_OVER_SAMPLE_QUOTA = "PAYWALL_OVER_SAMPLE_QUOTA"

    @classmethod
    def record(cls, session, url: str, feed, content_simhash, reason):
        url_object = Url.find_or_create(session, url)
        if url_object is None:
            return
        row = cls.query.filter_by(url_id=url_object.id).first() or cls(url=url_object)
        row.feed_id = feed.id
        row.content_simhash = content_simhash
        row.reason = reason
        row.skipped_at = datetime.now()
        session.add(row)

    @classmethod
    def find(cls, url: str):
        try:
            url_object = Url.find(url)
        except NoResultFound:
            return None
        return cls.query.filter_by(url_id=url_object.id).first()

    @classmethod
    def simhashes_of_feed_since(cls, feed, since):
        """(simhash, reason) of the feed's recent skips."""
        return (
            db.session.query(cls.content_simhash, cls.reason).filter(
                cls.feed_id == feed.id,
                cls.skipped_at >= since,
                cls.content_simhash.isnot(None),
            )
            .all()
        )
