import enum

from zeeguu.core.model.badge_level import BadgeLevel
from zeeguu.core.model.db import db

class BadgeCode(enum.Enum):
    TRANSLATED_WORDS = 'TRANSLATED_WORDS'
    CORRECT_EXERCISES= 'CORRECT_EXERCISES'
    COMPLETED_AUDIO_LESSONS = 'COMPLETED_AUDIO_LESSONS'
    STREAK_COUNT = 'STREAK_COUNT'
    LEARNED_WORDS = 'LEARNED_WORDS'
    READ_ARTICLES = 'READ_ARTICLES'

class Badge(db.Model):
    __tablename__ = "badge"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_hidden = db.Column(db.Boolean, default=False)

    # Constraints
    __table_args__ = (
        db.UniqueConstraint("code"),
    )

    # Relationships
    badge_levels = db.relationship(BadgeLevel, back_populates="badge", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Badge {self.name}>"

    @classmethod
    def find(cls, code: BadgeCode):
        """Find badge for a specific code"""
        return cls.query.filter_by(code=code.value).first()
