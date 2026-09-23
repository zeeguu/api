"""Public codes behind article links: zeeguu.org/read/<article code>?by=<user code>.

Two independent codes instead of one per (user, article) pair:

- ``ArticlePublicCode``: the article's address. 10 letters/digits (62^10), so
  article links can't be walked the way numeric ids can. Minted the first time
  the article gets a link and never changed -- unless deliberately rotated, which
  retires every link to that article at once.
- ``UserShareCode``: who shared. Short (6 chars): it's a credit, not a key --
  the article code is what opens the page. Rotating it drops that person's
  credit from every link they ever shared.

A logged-in reader's address bar shows the same link the Share button copies,
so each is written once (per article, per user), never per open.
"""

import secrets
import string

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User

ALPHABET = string.ascii_letters + string.digits  # no "-"/"_": chat apps cut them


def _random_code(length):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def _find_or_create(cls, session, owner_field, owner_id, length):
    existing = cls.query.filter_by(**{owner_field: owner_id}).first()
    if existing:
        return existing
    row = cls(**{owner_field: owner_id, "code": _random_code(length)})
    # A concurrent first open races the primary key; the savepoint keeps the
    # outer transaction usable and the winner's row is returned.
    try:
        with session.begin_nested():
            session.add(row)
        return row
    except Exception:
        return cls.query.filter_by(**{owner_field: owner_id}).one()


class ArticlePublicCode(db.Model):
    __tablename__ = "article_public_code"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    CODE_LENGTH = 10

    # A code must not keep an article alive: it cascades with the nightly prune.
    article_id = Column(Integer, ForeignKey("article.id", ondelete="CASCADE"), primary_key=True)
    code = Column(String(16), unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now())

    article = relationship("Article")

    @classmethod
    def for_article(cls, session, article_id):
        return _find_or_create(cls, session, "article_id", article_id, cls.CODE_LENGTH)

    @classmethod
    def find_article(cls, code):
        if not isinstance(code, str) or not code:
            return None
        row = cls.query.filter_by(code=code).first()
        return row.article if row else None


class UserShareCode(db.Model):
    __tablename__ = "user_share_code"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    CODE_LENGTH = 6

    user_id = Column(Integer, ForeignKey(User.id), primary_key=True)
    code = Column(String(16), unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now())

    user = relationship(User)

    @classmethod
    def for_user(cls, session, user_id):
        return _find_or_create(cls, session, "user_id", user_id, cls.CODE_LENGTH)

    @classmethod
    def sharer_name(cls, code):
        """First name of the person behind a ?by= code, for the "shared by"
        credit. None for unknown codes and anonymous app users (their name is
        a placeholder, "Guest")."""
        if not isinstance(code, str) or not code:
            return None
        row = cls.query.filter_by(code=code).first()
        if not row or row.user.is_anonymous():
            return None
        name = (row.user.name or row.user.username or "").strip()
        return name.split()[0] if name else None
