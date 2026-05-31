"""A per-(video, target_language, target_cefr) bundle of translated captions.

Owns the async-job status so the reader can poll while translation runs in the background.
Timing is NOT stored here — it stays on the original Caption rows so we don't duplicate it.
"""
from datetime import datetime

from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language
from zeeguu.core.model.video import Video


CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
STATUS_PENDING = "pending"
STATUS_TRANSLATING = "translating"
STATUS_READY = "ready"
STATUS_ERROR = "error"


class CaptionTranslationSet(db.Model):
    __tablename__ = "caption_translation_set"
    __table_args__ = (
        db.UniqueConstraint(
            "video_id",
            "target_language_id",
            "cefr_level",
            name="uq_caption_translation_set_video_lang_cefr",
        ),
        {"mysql_collate": "utf8_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)

    video_id = db.Column(db.Integer, db.ForeignKey(Video.id), nullable=False)
    video = db.relationship(Video)

    target_language_id = db.Column(db.Integer, db.ForeignKey(Language.id), nullable=False)
    target_language = db.relationship(Language)

    cefr_level = db.Column(
        db.Enum(*CEFR_LEVELS, name="cefr_level_enum"), nullable=False
    )

    status = db.Column(
        db.Enum(
            STATUS_PENDING, STATUS_TRANSLATING, STATUS_READY, STATUS_ERROR,
            name="caption_translation_set_status",
        ),
        nullable=False,
        default=STATUS_PENDING,
    )
    error_message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    translations = db.relationship(
        "CaptionTranslation", back_populates="translation_set", cascade="all, delete-orphan"
    )

    def __init__(self, video, target_language, cefr_level):
        self.video = video
        self.target_language = target_language
        self.cefr_level = cefr_level
        self.status = STATUS_PENDING
        self.created_at = datetime.utcnow()

    def __repr__(self):
        return (
            f"<CaptionTranslationSet video={self.video_id} "
            f"lang={self.target_language_id} cefr={self.cefr_level} status={self.status}>"
        )

    def mark_translating(self):
        self.status = STATUS_TRANSLATING
        self.error_message = None

    def mark_ready(self):
        self.status = STATUS_READY
        self.error_message = None

    def mark_error(self, message: str):
        self.status = STATUS_ERROR
        self.error_message = (message or "")[:500]

    def as_dictionary(self):
        return {
            "id": self.id,
            "video_id": self.video_id,
            "target_language": self.target_language.code,
            "cefr_level": self.cefr_level,
            "status": self.status,
            "error_message": self.error_message,
        }

    @classmethod
    def find_or_create(cls, session, video, target_language, cefr_level):
        """Idempotent: a second request for the same (video, lang, cefr) returns the existing
        set so callers can poll status without re-translating."""
        try:
            return (
                cls.query.filter_by(
                    video_id=video.id,
                    target_language_id=target_language.id,
                    cefr_level=cefr_level,
                ).one()
            )
        except NoResultFound:
            new_set = cls(video=video, target_language=target_language, cefr_level=cefr_level)
            session.add(new_set)
            session.commit()
            return new_set

    @classmethod
    def find_by_id(cls, set_id: int):
        return cls.query.filter_by(id=set_id).first()
