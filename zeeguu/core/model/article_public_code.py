import secrets
import string

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db


class ArticlePublicCode(db.Model):
    """An article's public address: zeeguu.org/read/<code>.

    Numeric ids never appear in links people share: they can be walked, and
    the public page would then let anyone copy articles out one by one. The
    code is 10 random letters/digits (62^10), minted the first time the article
    gets a link and the same for everyone -- a reader's address bar and the
    Share button give the same URL. Rotating it retires every link at once.
    """

    __tablename__ = "article_public_code"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    CODE_LENGTH = 10
    # No "-" or "_": chat apps tend to cut them off the end of a link.
    ALPHABET = string.ascii_letters + string.digits

    # A code must not keep an article alive: it cascades with the nightly prune.
    article_id = Column(Integer, ForeignKey("article.id", ondelete="CASCADE"), primary_key=True)
    code = Column(String(16), unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now())

    article = relationship("Article")

    @classmethod
    def for_article(cls, session, article_id):
        existing = cls.query.filter_by(article_id=article_id).first()
        if existing:
            return existing
        row = cls(article_id=article_id, code="".join(secrets.choice(cls.ALPHABET) for _ in range(cls.CODE_LENGTH)))
        # Two readers opening a never-linked article at once race the primary
        # key; the savepoint keeps the outer transaction usable, winner's code wins.
        try:
            with session.begin_nested():
                session.add(row)
            return row
        except Exception:
            return cls.query.filter_by(article_id=article_id).one()

    @classmethod
    def find_article(cls, code):
        if not isinstance(code, str) or not code:
            return None
        row = cls.query.filter_by(code=code).first()
        return row.article if row else None
