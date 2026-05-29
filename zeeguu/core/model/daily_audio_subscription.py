from datetime import datetime, timedelta

from sqlalchemy import (
    Column,
    Integer,
    Boolean,
    String,
    SmallInteger,
    TIMESTAMP,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.language import Language


class DailyAudioSubscription(db.Model):
    """Per-(user, language) config for the daily audio lesson: what to generate,
    whether it's on, and on which days.

    This owns CONFIG only (type / subject / enabled / schedule). The engagement
    "pause" (don't pile up unheard lessons) is NOT stored here — it's computed
    from the latest lesson by DailyAudioLesson.waiting_paused_for / is_engaged
    (introduced in #643), which this model reuses rather than duplicates.

    A row means the learner set up daily lessons for this language. enabled=False
    is a deliberate turn-off (config remembered). No row = never subscribed.
    """

    __tablename__ = "daily_audio_subscription"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "language_id", name="uq_daily_audio_subscription_user_lang"
        ),
        {"mysql_collate": "utf8mb4_unicode_ci"},
    )

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    user = relationship(User)

    language_id = Column(Integer, ForeignKey(Language.id), nullable=False)
    language = relationship(Language)

    enabled = Column(Boolean, default=True, nullable=False)

    lesson_type = Column(String(20), nullable=False)  # three_words_lesson | topic | situation
    raw_suggestion = Column(String(255), nullable=True)

    schedule_kind = Column(String(20), default="daily", nullable=False)  # daily | weekdays
    weekday_mask = Column(SmallInteger, default=127)  # Mon=bit0 .. Sun=bit6

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, user, language, lesson_type, raw_suggestion=None):
        self.user = user
        self.language = language
        self.lesson_type = lesson_type
        self.raw_suggestion = raw_suggestion
        self.enabled = True
        self.schedule_kind = "daily"
        self.weekday_mask = 127

    def __repr__(self):
        return (
            f"<DailyAudioSubscription user={self.user_id} lang={self.language_id} "
            f"type={self.lesson_type} enabled={self.enabled}>"
        )

    # --- transitions (mutating; caller commits) ---------------------------

    def configure(self, lesson_type, raw_suggestion):
        self.lesson_type = lesson_type
        self.raw_suggestion = raw_suggestion
        self.enabled = True

    def set_enabled(self, enabled):
        self.enabled = enabled

    # --- schedule ---------------------------------------------------------

    def scheduled_on(self, day):
        """Whether `day` is a generation day for this subscription's schedule."""
        if self.schedule_kind == "weekdays":
            return bool((self.weekday_mask or 0) & (1 << day.weekday()))
        return True  # daily

    def next_lesson_date(self, today_local, has_lesson_today, is_paused):
        """Date of the next lesson, or None when there's no fixed date — either
        the subscription is off, or generation is paused waiting for the learner
        to engage with the current lesson (see DailyAudioLesson.waiting_paused_for)."""
        if not self.enabled or is_paused:
            return None
        start = today_local + timedelta(days=1) if has_lesson_today else today_local
        if self.schedule_kind == "weekdays":
            for i in range(8):
                day = start + timedelta(days=i)
                if self.scheduled_on(day):
                    return day
            return None
        return start  # daily

    # --- lookups ----------------------------------------------------------

    @classmethod
    def find(cls, user, language):
        return cls.query.filter_by(user_id=user.id, language_id=language.id).first()

    @classmethod
    def find_or_create(cls, session, user, language, lesson_type, raw_suggestion=None):
        sub = cls.find(user, language)
        if sub is None:
            sub = cls(user, language, lesson_type, raw_suggestion)
            session.add(sub)
            session.flush()
        return sub
