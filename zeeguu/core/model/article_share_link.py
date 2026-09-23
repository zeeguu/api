from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.article import Article


class ArticleShareLink(db.Model):
    """LEGACY: one share code per (user, article), from links shaped
    /read/article?id=<id>&s=<code> that were handed out on 2026-09-23.

    Superseded by public_codes (zeeguu.org/read/<article code>.<sharer code>).
    Kept only so those links can still be resolved and redirected; nothing
    creates rows any more.
    """

    __tablename__ = "article_share_link"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_article_share_link_user_article"),
        {"mysql_collate": "utf8_bin"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(16), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("article.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())

    user = relationship(User)
    article = relationship(Article)

    @classmethod
    def find_for_article(cls, code, article_id):
        """The link with this code, only if it was minted for this article."""
        if not code:
            return None
        return cls.query.filter_by(code=code, article_id=article_id).first()
