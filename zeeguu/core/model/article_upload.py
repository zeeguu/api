"""Per-user ingestion entity for extension / share uploads.

We persist the extras the client already extracted with Readability
(title, image_url, author, language) alongside raw_html/text_content,
so the choice modal can render a proper preview immediately and the
conversion endpoint doesn't pay a second readability_server pass when
deriving the Article.
"""
from datetime import datetime

from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UnicodeText
from sqlalchemy.orm import joinedload, relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language
from zeeguu.core.model.url import Url
from zeeguu.core.model.user import User

# langdetect only needs a few KB; don't feed it full raw_html.
_LANGDETECT_MAX_CHARS = 4000

_DEFAULT_USER_UPLOADS_LIMIT = 100


class ArticleUpload(db.Model):
    __tablename__ = "article_upload"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    user = relationship(User)

    url_id = Column(Integer, ForeignKey(Url.id), nullable=False)
    url = relationship(Url)

    language_id = Column(Integer, ForeignKey(Language.id), nullable=False)
    language = relationship(Language)

    # The canonical article at this upload's URL (many uploads : one article).
    # NULL until an article exists at the URL. The full body stays HERE, in the
    # upload — it is never written into `article` (which may be recommended),
    # so one subscriber's paywall access can't leak into the corpus.
    article_id = Column(Integer, ForeignKey("article.id"), nullable=True)
    article = relationship("Article", foreign_keys=[article_id])

    title = Column(String(512))
    raw_html = Column(UnicodeText())
    text_content = Column(UnicodeText())
    image_url = Column(String(2048))
    author = Column(String(256))

    created_at = Column(DateTime, nullable=False)

    def __init__(self, user, url, language, title=None, raw_html=None,
                 text_content=None, image_url=None, author=None):
        self.user = user
        self.url = url
        self.language = language
        self.title = title
        self.raw_html = raw_html
        self.text_content = text_content
        self.image_url = image_url
        self.author = author
        self.created_at = datetime.now()

    def __repr__(self):
        return f"<ArticleUpload {self.id} user={self.user_id} url={self.url_id}>"

    @classmethod
    def find_by_id(cls, upload_id):
        return cls.query.filter_by(id=upload_id).first()

    def canonical_article(self, session, create=False):
        """The canonical Article at this upload's URL, linking it if needed.

        This is the *handle* the reader/share stack consumes — NOT where the
        full body lives (that stays in ``text_content`` here). We resolve it by
        URL, and when ``create`` we build a public article FROM THE URL ONLY —
        never from this upload's ``text_content``/``raw_html`` — so a
        subscriber's full paywalled body is never laundered into a row that the
        recommender could serve. A common crawl stub at the URL is the correct
        handle; the recipient's full-body derivative is generated separately
        from ``text_content``.

        Returns the Article (and caches it on ``article_id``), or ``None`` if
        no article exists and ``create`` is False.
        """
        from zeeguu.core.model.article import Article

        if self.article is not None:
            return self.article

        url_string = self.url.as_string()
        existing = Article.find(url_string)
        if existing is None and create:
            # URL only — deliberately no text_content/raw_html (see docstring).
            existing = Article.find_or_create(session, url_string)

        if existing is not None:
            self.article_id = existing.id
            session.add(self)
            session.commit()
        return existing

    @classmethod
    def for_user(cls, user, limit=_DEFAULT_USER_UPLOADS_LIMIT):
        return (
            cls.query.options(joinedload(cls.url), joinedload(cls.language))
            .filter_by(user_id=user.id)
            .order_by(cls.created_at.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def find_or_create(cls, session, user, url_string, raw_html, text_content,
                       title=None, image_url=None, author=None, language_code=None):
        lang_code = language_code
        if not lang_code:
            detection_basis = (text_content or raw_html or title or "")[:_LANGDETECT_MAX_CHARS]
            try:
                lang_code = detect(detection_basis) if detection_basis else None
            except LangDetectException:
                lang_code = None
        language = Language.find(lang_code) if lang_code else None

        url_obj = Url.find_or_create(session, url_string, title=title or "")

        existing = cls.query.filter_by(user_id=user.id, url_id=url_obj.id).first()
        if existing:
            existing.raw_html = raw_html
            existing.text_content = text_content
            existing.title = title
            existing.image_url = image_url
            existing.author = author
            existing.language = language
            session.add(existing)
            session.commit()
            # Link to a crawl already at this URL, if any (cheap — never creates).
            existing.canonical_article(session, create=False)
            return existing

        upload = cls(
            user=user,
            url=url_obj,
            language=language,
            title=title,
            raw_html=raw_html,
            text_content=text_content,
            image_url=image_url,
            author=author,
        )
        session.add(upload)
        session.commit()
        # Link to a crawl already at this URL, if any (cheap — never creates).
        upload.canonical_article(session, create=False)
        return upload

    def as_dictionary(self):
        # Key is `img_url` to match /detect_article_info and the rest of the
        # web client (article.img_url, ArticlePreview, etc.) — the share-flow
        # consumer reads the same field regardless of which endpoint fed it.
        return {
            "id": self.id,
            "url": self.url.as_string() if self.url else None,
            "title": self.title,
            "language": self.language.code if self.language else None,
            "img_url": self.image_url,
            "author": self.author,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
