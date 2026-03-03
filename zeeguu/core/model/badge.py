import enum

from zeeguu.core.model.badge_level import BadgeLevel
from zeeguu.core.model.db import db


class BadgeCode(enum.Enum):
    """Enum representing all available badge codes in the system."""
    TRANSLATED_WORDS = 'TRANSLATED_WORDS'
    CORRECT_EXERCISES = 'CORRECT_EXERCISES'
    COMPLETED_AUDIO_LESSONS = 'COMPLETED_AUDIO_LESSONS'
    STREAK_COUNT = 'STREAK_COUNT'
    LEARNED_WORDS = 'LEARNED_WORDS'
    READ_ARTICLES = 'READ_ARTICLES'


class Badge(db.Model):
    """
       Represents a badge that can be earned by users. Each badge can have
       multiple levels defined in BadgeLevel.
    """
    __tablename__ = "badge"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Enum(BadgeCode), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.UniqueConstraint("code"),
    )

    badge_levels = db.relationship(BadgeLevel, back_populates="badge", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Badge {self.name}>"

    @classmethod
    def find(cls, code: BadgeCode) -> "Badge":
        """
        Find a badge by its BadgeCode enum value.

        Returns:
            Badge object if found, else None.
        """
        return cls.query.filter_by(code=code).first()
