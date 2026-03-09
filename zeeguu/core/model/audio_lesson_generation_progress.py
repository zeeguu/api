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

    # Track which word we're on (for "Word 2 of 3" display)
    current_word = Column(Integer, default=0)
    total_words = Column(Integer, default=0)

    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, user, total_words=3):
        self.user = user
        self.total_words = total_words
        self.current_word = 0
        self.current_step = 0
        self.total_steps = 0
        self.status = "pending"

    def __repr__(self):
        return f"<AudioLessonGenerationProgress user={self.user_id} status={self.status}>"

    def start_word(self, word_number, total_segments, word_name=None):
        """Called when starting to process a new word."""
        self.current_word = word_number
        self.total_steps = total_segments
        self.current_step = 0
        self.status = "generating_script"
        self._current_word_name = word_name
        label = f"'{word_name}'" if word_name else f"word {word_number}"
        self.message = f"Word {word_number}/{self.total_words} ({label}): Generating script..."
        db.session.flush()

    def update_generating_script(self):
        """Called when starting to generate the script for current word."""
        self.status = "generating_script"
        label = f"'{self._current_word_name}'" if getattr(self, '_current_word_name', None) else f"word {self.current_word}"
        self.message = f"Word {self.current_word}/{self.total_words} ({label}): Generating script..."
        db.session.flush()

    def update_script_done(self):
        """Called when script generation is complete."""
        self.status = "synthesizing_audio"
        label = f"'{self._current_word_name}'" if getattr(self, '_current_word_name', None) else f"word {self.current_word}"
        self.message = f"Word {self.current_word}/{self.total_words} ({label}): Synthesizing audio..."
        db.session.flush()

    def update_segment(self, segment_number, total_segments, voice_type):
        """Called when synthesizing each audio segment."""
        self.current_step = segment_number
        self.total_steps = total_segments
        label = f"'{self._current_word_name}'" if getattr(self, '_current_word_name', None) else f"word {self.current_word}"
        self.message = f"Word {self.current_word}/{self.total_words} ({label}): Synthesizing {voice_type} voice ({segment_number}/{total_segments})"
        db.session.flush()

    def update_combining(self):
        """Called when combining audio segments."""
        self.status = "combining_audio"
        label = f"'{self._current_word_name}'" if getattr(self, '_current_word_name', None) else f"word {self.current_word}"
        self.message = f"Word {self.current_word}/{self.total_words} ({label}): Combining audio..."
        db.session.flush()

    def mark_done(self):
        """Called when generation is complete."""
        self.status = "done"
        self.current_step = self.total_steps
        self.message = "Audio lesson ready!"
        db.session.flush()

    def mark_error(self, error_message):
        """Called when an error occurs."""
        self.status = "error"
        self.message = error_message[:255] if error_message else "Unknown error"
        db.session.flush()

    def to_dict(self):
        """Convert to dictionary for API response."""
        return {
            "status": self.status,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "current_word": self.current_word,
            "total_words": self.total_words,
            "message": self.message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }

    @classmethod
    def find_for_user(cls, user):
        """Find the most recent progress record for a user."""
        return (
            cls.query.filter_by(user_id=user.id)
            .order_by(cls.started_at.desc())
            .first()
        )

    @classmethod
    def find_active_for_user(cls, user):
        """Find an active (in-progress) generation for a user."""
        return (
            cls.query.filter_by(user_id=user.id)
            .filter(cls.status.notin_(["done", "error"]))
            .first()
        )

    @classmethod
    def create_for_user(cls, user, total_words=3):
        """Create a new progress record, deleting any old ones."""
        # Delete old progress records for this user
        cls.query.filter_by(user_id=user.id).delete()

        progress = cls(user=user, total_words=total_words)
        db.session.add(progress)
        db.session.flush()
        return progress

    @classmethod
    def cleanup_old_records(cls, hours=1):
        """Delete progress records older than specified hours."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cls.query.filter(cls.started_at < cutoff).delete()
        db.session.commit()
