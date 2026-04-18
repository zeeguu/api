from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User


class AudioLessonGenerationProgress(db.Model):
    """
    Tracks the progress of audio lesson generation for real-time UI updates.
    Records are temporary and should be cleaned up after completion.
    Only one generation per user at a time is allowed.
    """

    __tablename__ = "audio_lesson_generation_progress"
    __table_args__ = {"mysql_collate": "utf8mb4_unicode_ci"}

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id, ondelete="CASCADE"), nullable=False)
    user = relationship(User)

    status = Column(
        Enum(
            "pending",
            "generating_script",
            "synthesizing_audio",
            "combining_audio",
            "done",
            "error",
            name="generation_status",
        ),
        default="pending",
    )

    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    message = Column(String(255), nullable=True)

    current_segment = Column(Integer, default=0)
    total_segments = Column(Integer, default=0)

    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, user, total_segments=1):
        self.user = user
        self.total_segments = total_segments
        self.current_segment = 0
        self.current_step = 0
        self.total_steps = 0
        self.status = "pending"

    def __repr__(self):
        return f"<AudioLessonGenerationProgress user={self.user_id} status={self.status}>"

    def _segment_prefix(self):
        name = getattr(self, '_current_segment_name', None)
        if self.total_segments == 1 and name:
            return name
        if name:
            return f"Segment {self.current_segment}/{self.total_segments} ({name})"
        return f"Segment {self.current_segment}/{self.total_segments}"

    def start_segment(self, segment_number, segment_name=None):
        """Called when starting to process a new segment."""
        self.current_segment = segment_number
        self.current_step = 0
        self.total_steps = 0
        self.status = "generating_script"
        self._current_segment_name = segment_name
        self.message = f"{self._segment_prefix()}: Generating script..."
        db.session.flush()

    def update_generating_script(self):
        self.status = "generating_script"
        self.message = f"{self._segment_prefix()}: Generating script..."
        db.session.flush()

    def update_script_done(self):
        self.status = "synthesizing_audio"
        self.message = f"{self._segment_prefix()}: Synthesizing audio..."
        db.session.flush()

    def update_segment(self, step_number, total_steps, voice_type):
        """Called when synthesizing each audio segment."""
        self.current_step = step_number
        self.total_steps = total_steps
        self.message = f"{self._segment_prefix()}: Synthesizing {voice_type} voice ({step_number}/{total_steps})"
        db.session.flush()

    def update_combining(self):
        self.status = "combining_audio"
        self.message = f"{self._segment_prefix()}: Combining audio..."
        db.session.flush()

    def mark_done(self):
        self.status = "done"
        self.current_step = self.total_steps
        self.message = "Audio lesson ready!"
        db.session.flush()

    def mark_error(self, error_message):
        self.status = "error"
        self.message = error_message[:255] if error_message else "Unknown error"
        db.session.flush()

    def to_dict(self):
        return {
            "status": self.status,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "current_segment": self.current_segment,
            "total_segments": self.total_segments,
            "message": self.message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }

    @classmethod
    def find_for_user(cls, user):
        return (
            cls.query.filter_by(user_id=user.id)
            .order_by(cls.started_at.desc())
            .first()
        )

    @classmethod
    def find_active_for_user(cls, user):
        return (
            cls.query.filter_by(user_id=user.id)
            .filter(cls.status.notin_(["done", "error"]))
            .first()
        )

    @classmethod
    def create_for_user(cls, user, total_segments=1):
        cls.query.filter_by(user_id=user.id).delete()
        progress = cls(user=user, total_segments=total_segments)
        db.session.add(progress)
        db.session.flush()
        return progress

    @classmethod
    def cleanup_old_records(cls, hours=1):
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cls.query.filter(cls.started_at < cutoff).delete()
        db.session.commit()
