"""What the cleanup of an upload removed (content_cleaning/upload_cleanup.py), kept to check it and to
train a cheaper classifier on later: the upload as it came, and the decision on each of its blocks."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, UnicodeText
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from zeeguu.core.model.db import db

LONG_TEXT = UnicodeText().with_variant(MEDIUMTEXT(charset="utf8mb4"), "mysql")


class ArticleUploadCleanup(db.Model):
    __tablename__ = "article_upload_cleanup"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_bin"}

    upload_id = Column(Integer, ForeignKey("article_upload.id", ondelete="CASCADE"), primary_key=True)
    original_html = Column(LONG_TEXT)
    original_text = Column(LONG_TEXT)
    incomplete = Column(Boolean, nullable=False)
    incomplete_note = Column(UnicodeText())
    model = Column(String(64), nullable=False)
    prompt_version = Column(Integer, nullable=False)
    seconds = Column(Float)
    created_at = Column(DateTime, nullable=False)

    def __init__(self, upload, original_html, original_text, incomplete, incomplete_note, model, prompt_version, seconds):
        self.upload_id = upload.id
        self.original_html = original_html
        self.original_text = original_text
        self.incomplete = incomplete
        self.incomplete_note = incomplete_note
        self.model = model
        self.prompt_version = prompt_version
        self.seconds = seconds
        self.created_at = datetime.now()


class ArticleUploadBlock(db.Model):
    __tablename__ = "article_upload_block"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_bin"}

    id = Column(Integer, primary_key=True)
    upload_id = Column(Integer, ForeignKey("article_upload.id", ondelete="CASCADE"), nullable=False, index=True)
    block_i = Column(Integer, nullable=False)
    text = Column(UnicodeText(), nullable=False)
    kept = Column(Boolean, nullable=False)
    reason = Column(String(32))
    note = Column(UnicodeText())

    def __init__(self, upload, block_i, text, kept, reason=None, note=None):
        self.upload_id = upload.id
        self.block_i = block_i
        self.text = text
        self.kept = kept
        self.reason = reason
        self.note = note
