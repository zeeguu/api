from datetime import datetime
from sqlalchemy import Column, Integer, Text, JSON, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.language import Language


class DailyAudioLesson(db.Model):
    """
    Daily audio lesson that combines multiple meaning lessons for a user.
    MP3 files are stored on disk with filename pattern: {id}.mp3
    Tracks user interaction including completion status and pause/resume functionality.
    """

    __tablename__ = "daily_audio_lesson"
    __table_args__ = {"mysql_collate": "utf8mb4_unicode_ci"}

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    user = relationship(User, backref="daily_audio_lessons")

    language_id = Column(Integer, ForeignKey(Language.id), nullable=True)
    language = relationship(Language)

    voice_config = Column(JSON)
    duration_seconds = Column(Integer)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    created_by = Column(db.String(255), nullable=False)

    # User interaction tracking
    recommended_at = Column(TIMESTAMP, default=datetime.utcnow)
    completed_at = Column(TIMESTAMP)
    listened_count = Column(Integer, default=0)

    # Pause/resume tracking
    last_paused_at = Column(TIMESTAMP)
    pause_position_seconds = Column(Integer, default=0)

    # Relationship to segments (individual meaning lessons)
    segments = relationship(
        "DailyAudioLessonSegment",
        back_populates="daily_lesson",
        order_by="DailyAudioLessonSegment.sequence_order",
        cascade="all, delete-orphan",
    )

    def __init__(self, user, created_by, voice_config=None, duration_seconds=None, language=None):
        self.user = user
        self.created_by = created_by
        self.voice_config = voice_config
        self.duration_seconds = duration_seconds
        self.language = language or user.learned_language
        self.listened_count = 0
        self.pause_position_seconds = 0

    def __repr__(self):
        return f"<DailyAudioLesson {self.id} for user {self.user_id}>"

    @property
    def audio_file_path(self):
        """Returns the expected path for the audio file based on lesson ID"""
        return f"/audio/daily_lessons/{self.id}.mp3"

    def add_intro_segment(self, daily_audio_lesson_wrapper, sequence_order=1):
        """Add intro segment to this daily lesson"""
        from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment

        segment = DailyAudioLessonSegment(
            daily_lesson=self,
            segment_type="intro",
            daily_audio_lesson_wrapper=daily_audio_lesson_wrapper,
            sequence_order=sequence_order,
        )
        self.segments.append(segment)
        return segment

    def add_meaning_segment(self, audio_lesson_meaning, sequence_order):
        """Add a meaning lesson segment to this daily lesson"""
        from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment
        from zeeguu.core.model import db

        segment = DailyAudioLessonSegment(
            daily_lesson=self,
            segment_type="meaning_lesson",
            audio_lesson_meaning=audio_lesson_meaning,
            sequence_order=sequence_order,
        )
        # Only add to session - the relationship will be handled automatically
        db.session.add(segment)
        return segment

    def add_outro_segment(self, daily_audio_lesson_wrapper, sequence_order):
        """Add outro segment to this daily lesson"""
        from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment

        segment = DailyAudioLessonSegment(
            daily_lesson=self,
            segment_type="outro",
            daily_audio_lesson_wrapper=daily_audio_lesson_wrapper,
            sequence_order=sequence_order,
        )
        self.segments.append(segment)
        return segment

    @property
    def meaning_count(self):
        """Number of meanings included in this daily lesson"""
        return sum(1 for s in self.segments if s.segment_type == "meaning_lesson")

    def mark_completed(self):
        """Mark this lesson as completed"""
        self.completed_at = datetime.utcnow()
        self.listened_count += 1
        self.pause_position_seconds = 0

    def pause_at(self, position_seconds):
        """Record pause position for later resume"""
        self.last_paused_at = datetime.now()
        self.pause_position_seconds = position_seconds

    def resume(self):
        """Increment listen count when resuming"""
        self.listened_count += 1

    @property
    def is_completed(self):
        """Check if lesson has been completed"""
        return self.completed_at is not None

    @property
    def is_paused(self):
        """Check if lesson is currently paused"""
        return self.pause_position_seconds > 0 and not self.is_completed

    @classmethod
    def find_latest_for_user(cls, user, include_completed=False):
        """Find the most recent audio lesson for a user"""
        query = cls.query.filter_by(user=user)
        if not include_completed:
            query = query.filter(cls.completed_at.is_(None))
        return query.order_by(cls.recommended_at.desc()).first()
