"""
A meaning lesson we could not get written under one prompt version: the model
declined (NotAScript) or the script stayed wrong after a rewrite
(LessonNotCorrect). The audio word selector skips the meaning for learners
with that teacher language until the prompt version changes. See the
migration 26-10-19--add_audio_lesson_refusal.sql.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language
from zeeguu.core.model.meaning import Meaning


class AudioLessonRefusal(db.Model):
    __tablename__ = "audio_lesson_refusal"
    # The key the migration creates, declared so create_all builds it too
    __table_args__ = (
        UniqueConstraint(
            "meaning_id", "teacher_language_id", "prompt_version", name="uq_audio_lesson_refusal"
        ),
        {"mysql_collate": "utf8mb4_unicode_ci"},
    )

    NOT_A_SCRIPT = "not_a_script"
    NOT_CORRECT = "not_correct"

    id = Column(Integer, primary_key=True)
    meaning_id = Column(Integer, ForeignKey(Meaning.id, ondelete="CASCADE"), nullable=False)
    teacher_language_id = Column(Integer, ForeignKey(Language.id), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    reason = Column(Enum(NOT_A_SCRIPT, NOT_CORRECT, name="audio_lesson_refusal_reason"), nullable=False)
    detail = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    @classmethod
    def record(cls, session, meaning_id, teacher_language_id, prompt_version, reason, detail):
        """Does not commit. A refusal already recorded for this prompt version
        (another process got there first) is left as it is."""
        try:
            with session.begin_nested():
                session.add(
                    cls(
                        meaning_id=meaning_id,
                        teacher_language_id=teacher_language_id,
                        prompt_version=prompt_version,
                        reason=reason,
                        detail=detail,
                    )
                )
        except IntegrityError:
            pass
