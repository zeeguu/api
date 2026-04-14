"""Per-user ingestion entity for extension / share uploads."""
from datetime import datetime

from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import MEDIUMTEXT
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

    title = Column(String(512))
    raw_html = Column(MEDIUMTEXT)
    text_content = Column(MEDIUMTEXT)
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
    def create(cls, session, user, url_string, raw_html, text_content,
               title=None, image_url=None, author=None):
        detection_basis = (text_content or raw_html or title or "")[:_LANGDETECT_MAX_CHARS]
        try:
            lang_code = detect(detection_basis) if detection_basis else None
        except LangDetectException:
            lang_code = None
        language = Language.find(lang_code) if lang_code else None

        url_obj = Url.find_or_create(session, url_string, title=title or "")

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
        return upload

    def as_dictionary(self):
        return {
            "id": self.id,
            "url": self.url.as_string() if self.url else None,
            "title": self.title,
            "language": self.language.code if self.language else None,
            "image_url": self.image_url,
            "author": self.author,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
