import secrets
import string

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.article import Article


class ArticleShareLink(db.Model):
    """A user's public share link for one article (copied into WhatsApp etc.).

    The link is ``zeeguu.org/s/<code>``; the code alone identifies the article
    and the sharer. (``/read/article?id=<article_id>&s=<code>`` is what it
    resolves to, and what the first links looked like.) The opaque code lets
    the public page say who shared it without putting a user id or a forgeable
    name in the URL. One row per (user, article), so re-sharing the same
    article reuses the same link.

    Also what lets the public page open a text someone *uploaded*: those are
    private by default, and only a link its reader was actually sent unlocks one.
    """

    __tablename__ = "article_share_link"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_article_share_link_user_article"),
        {"mysql_collate": "utf8_bin"},
    )

    # Letters and digits only: 62^10 ~ 8e17 codes, far past guessing. No "-"
    # or "_" (as token_urlsafe would give): chat apps tend to cut them off the
    # end of a link. Codes minted before this may still contain them.
    CODE_LENGTH = 10
    CODE_ALPHABET = string.ascii_letters + string.digits

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(16), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("article.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())

    user = relationship(User)
    article = relationship(Article)

    def __init__(self, user_id: int, article_id: int):
        self.user_id = user_id
        self.article_id = article_id
        self.code = "".join(secrets.choice(self.CODE_ALPHABET) for _ in range(self.CODE_LENGTH))

    @classmethod
    def find_or_create(cls, session, user_id: int, article_id: int):
        existing = cls.query.filter_by(user_id=user_id, article_id=article_id).first()
        if existing:
            return existing
        link = cls(user_id, article_id)
        # Concurrent double-tap on "share" would race the unique (user, article)
        # index; the savepoint keeps the outer transaction usable if we lose.
        try:
            with session.begin_nested():
                session.add(link)
            return link
        except Exception:
            return cls.query.filter_by(user_id=user_id, article_id=article_id).one()

    @classmethod
    def find_by_code(cls, code):
        if not code:
            return None
        return cls.query.filter_by(code=code).first()

    @classmethod
    def find_for_article(cls, code, article_id):
        """The link with this code, only if it was minted for this article."""
        if not code:
            return None
        return cls.query.filter_by(code=code, article_id=article_id).first()

    def sharer_display_name(self):
        """First name only: the page is public, so don't print a full name.
        None for anonymous app users, whose name is a placeholder ("Guest")."""
        if self.user.is_anonymous():
            return None
        name = (self.user.name or self.user.username or "").strip()
        return name.split()[0] if name else None
