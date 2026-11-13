"""
Short texts a learner brings to read word by word: a WhatsApp message, a
paragraph from a mail, pasted or shared from another app. No title, read as
they are; a long text with a title is an Article the learner uploaded instead.

ShortText is the content, once: a Source of type ShortText, which already
deduplicates by (content, language), so the same message shared by two parents
of the same club is stored and tokenized once. UserShortText is a learner's
own list of them. When the last learner forgets a text, the text itself is
deleted (see UserShortText.forget). Nothing here is ever recommended or shown
to anyone but the learners who added it.
"""

import json
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UnicodeText, UniqueConstraint
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.race_safe import find_or_create
from zeeguu.core.model.source import Source
from zeeguu.core.model.source_text import SourceText
from zeeguu.core.model.source_type import SourceType
from zeeguu.core.model.user import User


class ShortText(db.Model):
    __tablename__ = "short_text"
    __table_args__ = (
        UniqueConstraint("source_id", name="short_text_source_unique"),
        {"mysql_collate": "utf8mb4_bin"},
    )

    id = Column(Integer, primary_key=True)

    source_id = Column(Integer, ForeignKey(Source.id), nullable=False)
    source = relationship(Source)

    created_at = Column(DateTime, nullable=False)

    # The tokens the reader gets, as JSON; computed on the first read. The
    # text never changes, so it is tokenized (and its MWEs found) once.
    tokenized_paragraphs = Column(UnicodeText)

    def __init__(self, source):
        self.source = source
        self.created_at = datetime.now()

    @property
    def content(self):
        return self.source.get_content()

    @property
    def language(self):
        return self.source.language

    def tokens(self, session, tokenize):
        """The cached tokens, computed with `tokenize(content, language)` the first time."""
        if self.tokenized_paragraphs is None:
            self.tokenized_paragraphs = json.dumps(tokenize(self.content, self.language))
            session.add(self)
        return json.loads(self.tokenized_paragraphs)

    @classmethod
    def find_by_id(cls, short_text_id):
        return cls.query.filter_by(id=short_text_id).one_or_none()

    @classmethod
    def find_or_create(cls, session, content, language):
        source_type = SourceType.find_by_type(SourceType.SHORT_TEXT)
        source_text = SourceText.find_or_create(session, content, commit=False)
        # Not Source.find_or_create: nothing keeps (text, type, language)
        # unique, so two learners adding the same text at once can make two
        # Sources, and its .one() would then fail on every later add. Here a
        # duplicate is only a second copy.
        source = (
            Source.query.filter_by(source_text=source_text, source_type=source_type, language=language)
            .order_by(Source.id)
            .first()
        )
        if not source:
            source = Source(source_text, source_type, language)
            session.add(source)
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

    def forget(self, session):
        """
        Off the learner's list. When no learner has the text any more, the
        text goes too: it is often other people's messages. Words learned from
        it stay; their bookmarks keep only the sentence they were tapped in.
        """
        from zeeguu.core.model.bookmark import Bookmark
        from zeeguu.core.model.user_activitiy_data import UserActivityData

        short_text = self.short_text
        session.delete(self)
        session.flush()
        if UserShortText.query.filter_by(short_text_id=short_text.id).count():
            return

        source = short_text.source
        source_text = source.source_text
        for referencing in (Bookmark, UserActivityData):
            referencing.query.filter_by(source_id=source.id).update(
                {"source_id": None}, synchronize_session=False
            )
        session.delete(short_text)
        session.flush()
        session.delete(source)
        session.flush()
        # The same content can be another source's (an identical article)
        if source_text and not Source.query.filter_by(source_text_id=source_text.id).count():
            session.delete(source_text)

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
