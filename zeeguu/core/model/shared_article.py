from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language


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
    # The recipient's personalized copy ("the multiplexer out"): the language
    # they receive it in, and the generated derivative (NULL until it's ready).
    delivery_language_id = Column(Integer, ForeignKey("language.id"), nullable=True)
    delivery_article_id = Column(Integer, ForeignKey("article.id"), nullable=True)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=func.now())
    read_at = Column(DateTime, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)

    from_user = relationship(User, foreign_keys=[from_user_id])
    to_user = relationship(User, foreign_keys=[to_user_id])
    article = relationship(Article, foreign_keys=[article_id])
    delivery_article = relationship(Article, foreign_keys=[delivery_article_id])
    delivery_language = relationship(Language, foreign_keys=[delivery_language_id])

    def __init__(self, from_user_id: int, to_user_id: int, article_id: int, note: str = None,
                 delivery_language_id: int = None, delivery_article_id: int = None):
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.article_id = article_id
        self.note = note
        self.delivery_language_id = delivery_language_id
        self.delivery_article_id = delivery_article_id

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

    @staticmethod
    def resolve_shareable_original_id(session, article) -> int:
        """The id of the canonical article to store on a share.

        A share always points at the ONE canonical article — the real crawled
        row at the publisher URL, which is the reader/inbox handle. The
        recipient's full-body derivative is generated separately from the
        sharer's upload (``source_upload.text_content``); this method only
        resolves the handle and never writes a body anywhere.

          - **Upload-based copy** (carries ``source_upload_id``): the canonical
            article at the upload's URL, created from the URL if none exists yet
            — NEVER from the upload's body (that would launder paywalled text
            into a recommendable row). Falls back to the sharer's own article if
            a handle can't be built, so the share still goes through.
          - **Simplification of a crawl** (``parent_article_id``): its parent
            (which may itself be upload-based → resolve through it).
          - **Plain crawled original**: itself.

        Always falls back to :meth:`resolve_original_article_id` on any error,
        so a share never fails on a resolution edge case.

        See docs/future-work/article-body-provenance-and-sharing.md.
        """
        try:
            if article.source_upload_id and article.source_upload is not None:
                canonical = article.source_upload.canonical_article(session, create=True)
                if canonical is not None:
                    return canonical.id
                # No handle could be built — share the sharer's copy, don't fail.
                return article.id

            if article.parent_article_id:
                parent = Article.find_by_id(article.parent_article_id)
                if parent is not None:
                    return SharedArticle.resolve_shareable_original_id(session, parent)
                return article.parent_article_id

            return SharedArticle.resolve_original_article_id(article)
        except Exception as e:
            from zeeguu.logging import log

            log(
                f"resolve_shareable_original_id: falling back for article "
                f"{getattr(article, 'id', '?')}: {e}"
            )
            return SharedArticle.resolve_original_article_id(article)

    @staticmethod
    def compute_delivery_language(recipient, upload):
        """The (language, cefr_level) the recipient's copy is delivered in.

        The recipient's own profile decides it — never the sender:

          - the article's **source language if the recipient learns it**
            (→ simplify to their level; authentic text), else
          - the recipient's **primary learned language** (→ translate + adapt).

        Level is resolved for the chosen language, defaulting to A2 when the
        recipient has no declared level there yet.
        """
        from zeeguu.core.model.user_language import UserLanguage

        source_language = upload.language
        delivery_language = recipient.learned_language
        if source_language is not None:
            learned = UserLanguage.all_languages_for_user(recipient)
            if any(l.id == source_language.id for l in learned):
                delivery_language = source_language

        try:
            level = recipient.cefr_level_for_language(delivery_language)
        except Exception:
            level = "A2"
        return delivery_language, level

    @classmethod
    def create(cls, session, from_user_id: int, to_user_id: int, article_id: int, note: str = None,
               delivery_language_id: int = None, delivery_article_id: int = None):
        shared = cls(from_user_id, to_user_id, article_id, note,
                     delivery_language_id, delivery_article_id)
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
        # Show (and open) the recipient's personalized derivative once it's
        # ready — its title is in the recipient's language, and its parent_url
        # still points at the publisher for "See original". Until then, fall
        # back to the canonical article so the row isn't empty.
        display_article = self.delivery_article or self.article
        return {
            "id": self.id,
            "from_user_id": self.from_user_id,
            "from_user_name": self.from_user.name,
            "from_user_username": self.from_user.username,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "read": self.read_at is not None,
            "article": display_article.article_info(with_content=False),
            "delivery_ready": self.delivery_article_id is not None,
            "delivery_language": self.delivery_language.code if self.delivery_language else None,
        }
