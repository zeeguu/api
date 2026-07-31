from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.article import Article


class SharedArticle(db.Model):
    """One friend sharing one article with another, on-platform.

    ``article_id`` is always the ORIGINAL/parent article id, never the sharer's
    adapted or translated copy, so the recipient's reader adapts it to their own
    language and level on open. ``read_at`` / ``dismissed_at`` track the
    recipient's inbox state.
    """

    __tablename__ = "shared_article"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("article.id"), nullable=False)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=func.now())
    read_at = Column(DateTime, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)

    from_user = relationship(User, foreign_keys=[from_user_id])
    to_user = relationship(User, foreign_keys=[to_user_id])
    article = relationship(Article, foreign_keys=[article_id])

    def __init__(self, from_user_id: int, to_user_id: int, article_id: int, note: str = None):
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.article_id = article_id
        self.note = note

    @staticmethod
    def resolve_original_article_id(article) -> int:
        """The id of the original/parent article to store for a share.

        Adapted/simplified copies point at their parent via ``parent_article_id``.
        Translated copies (today) don't set a parent — they encode the origin in
        a ``URL#translated-from-...`` fragment — so fall back to the pre-fragment
        original. Anything else is already an original.
        """
        if article.parent_article_id:
            return article.parent_article_id

        url = article.url.as_string()
        fragment_marker = "#translated-from-"
        if fragment_marker in url:
            original_url = url.split(fragment_marker)[0]
            try:
                original = Article.find(original_url)
                if original:
                    return original.id
            except Exception:
                pass  # original not in the DB — fall through to using this article

        return article.id

    @classmethod
    def create(cls, session, from_user_id: int, to_user_id: int, article_id: int, note: str = None):
        shared = cls(from_user_id, to_user_id, article_id, note)
        session.add(shared)
        session.commit()
        return shared

    @classmethod
    def find_by_id(cls, shared_id):
        return cls.query.filter(cls.id == shared_id).first()

    @classmethod
    def inbox_for(cls, user_id: int):
        """Non-dismissed shares received by the user, newest first."""
        return (
            cls.query.filter(cls.to_user_id == user_id)
            .filter(cls.dismissed_at.is_(None))
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def unread_count_for(cls, user_id: int) -> int:
        return (
            cls.query.filter(cls.to_user_id == user_id)
            .filter(cls.read_at.is_(None))
            .filter(cls.dismissed_at.is_(None))
            .count()
        )

    def mark_read(self, session):
        if self.read_at is None:
            self.read_at = datetime.now()
            session.add(self)
            session.commit()

    def dismiss(self, session):
        self.dismissed_at = datetime.now()
        session.add(self)
        session.commit()

    def to_dict(self):
        return {
            "id": self.id,
            "from_user_id": self.from_user_id,
            "from_user_name": self.from_user.name,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "read": self.read_at is not None,
            "article": self.article.article_info(with_content=False),
        }
