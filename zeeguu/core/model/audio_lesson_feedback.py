from datetime import datetime

from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson


class AudioLessonFeedback(db.Model):
    """
    What a learner said about one daily audio lesson, after hearing it: one row
    per lesson and aspect (pace, repetition, length, situation). Tapping
    again on the same lesson changes the row's value, so the row is the
    learner's last word on that lesson.

    The next lessons are tuned from these rows (audio_lessons/lesson_tuning.py),
    and the study reads them to see, lesson by lesson, what each learner asked for.
    """

    __tablename__ = "audio_lesson_feedback"
    __table_args__ = (
        UniqueConstraint(
            "daily_audio_lesson_id", "aspect", name="uq_audio_lesson_feedback_lesson_aspect"
        ),
        {"mysql_collate": "utf8mb4_unicode_ci"},
    )

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    user = relationship(User)

    daily_audio_lesson_id = Column(
        Integer, ForeignKey(DailyAudioLesson.id, ondelete="CASCADE"), nullable=False
    )
    daily_audio_lesson = relationship(DailyAudioLesson)

    aspect = Column(String(20), nullable=False)
    # For "situation": "stay", or the situation the learner chose for next time.
    value = Column(String(128), nullable=False)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, user, lesson, aspect, value):
        self.user = user
        self.daily_audio_lesson = lesson
        self.aspect = aspect
        self.value = value

    @classmethod
    def set(cls, user, lesson, aspect, value):
        """Record (or change) the learner's answer for this lesson and aspect.
        The caller commits."""
        row = cls.query.filter_by(daily_audio_lesson_id=lesson.id, aspect=aspect).first()
        if row:
            row.value = value
        else:
            row = cls(user, lesson, aspect, value)
            db.session.add(row)
        return row

    @classmethod
    def for_lesson(cls, lesson):
        """{aspect: value} for one lesson."""
        rows = cls.query.filter_by(daily_audio_lesson_id=lesson.id).all()
        return {row.aspect: row.value for row in rows}

    @classmethod
    def history(cls, user, language_id):
        """The learner's rows for lessons in this language, oldest lesson first."""
        return (
            cls.query.join(DailyAudioLesson, DailyAudioLesson.id == cls.daily_audio_lesson_id)
            .filter(cls.user_id == user.id, DailyAudioLesson.language_id == language_id)
            .order_by(DailyAudioLesson.id, cls.id)
            .all()
        )
