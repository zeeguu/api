"""
Short texts a learner brings to read word by word: a WhatsApp message, a
paragraph from a mail, pasted or shared from another app. No title, read as
they are; a long text with a title is an Article the learner uploaded instead.

ShortText is the content, once: a Source of type ShortText, which already
deduplicates by (content, language), so the same message shared by two parents
of the same club is stored and tokenized once. UserShortText is a learner's
own list of them; deleting that row is how a learner forgets a text. Nothing
here is ever recommended or shown to anyone but the learners who added it.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.race_safe import find_or_create
from zeeguu.core.model.source import Source
from zeeguu.core.model.source_type import SourceType
from zeeguu.core.model.user import User


class ShortText(db.Model):
    __tablename__ = "short_text"
    __table_args__ = (
        UniqueConstraint("source_id", name="short_text_source_unique"),
        {"mysql_collate": "utf8_bin"},
    )

    id = Column(Integer, primary_key=True)

    source_id = Column(Integer, ForeignKey(Source.id), nullable=False)
    source = relationship(Source)

    created_at = Column(DateTime, nullable=False)

    def __init__(self, source):
        self.source = source
        self.created_at = datetime.now()

    @property
    def content(self):
        return self.source.get_content()

    @property
    def language(self):
        return self.source.language

    @classmethod
    def find_by_id(cls, short_text_id):
        return cls.query.filter_by(id=short_text_id).one_or_none()

    @classmethod
    def find_or_create(cls, session, content, language):
        source = Source.find_or_create(
            session,
            content,
            SourceType.find_by_type(SourceType.SHORT_TEXT),
            language,
            broken=0,
            commit=False,
        )
        session.flush()
        return find_or_create(session, cls, {"source_id": source.id}, lambda: cls(source))


class UserShortText(db.Model):
    __tablename__ = "user_short_text"
    __table_args__ = (
        UniqueConstraint("user_id", "short_text_id", name="user_short_text_unique"),
        {"mysql_collate": "utf8_bin"},
    )

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    user = relationship(User)

    short_text_id = Column(Integer, ForeignKey(ShortText.id), nullable=False)
    short_text = relationship(ShortText)

    created_at = Column(DateTime, nullable=False)
    # When the learner last brought or opened it; the list is newest first
    last_opened_at = Column(DateTime, nullable=False)

    PREVIEW_CHARS = 120

    def __init__(self, user, short_text):
        self.user = user
        self.short_text = short_text
        self.created_at = self.last_opened_at = datetime.now()

    @classmethod
    def find(cls, user, short_text_id):
        return cls.query.filter_by(user_id=user.id, short_text_id=short_text_id).one_or_none()

    @classmethod
    def add(cls, session, user, short_text):
        """The learner's row for this text, created or brought to the top."""
        row = find_or_create(
            session,
            cls,
            {"user_id": user.id, "short_text_id": short_text.id},
            lambda: cls(user, short_text),
        )
        row.last_opened_at = datetime.now()
        return row

    @classmethod
    def all_for(cls, user):
        return cls.query.filter_by(user_id=user.id).order_by(cls.last_opened_at.desc()).all()

    def as_list_item(self):
        content = self.short_text.content
        preview = " ".join(content.split())
        if len(preview) > self.PREVIEW_CHARS:
            preview = preview[: self.PREVIEW_CHARS].rstrip() + "…"
        return {
            "id": self.short_text_id,
            "preview": preview,
            "language": self.short_text.language.code,
            "last_opened_at": self.last_opened_at.isoformat(),
        }
