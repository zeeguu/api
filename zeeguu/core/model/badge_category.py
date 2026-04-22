import enum

from zeeguu.core.model.db import db


class ActivityMetric(enum.Enum):
    """Enum representing all available activity metrics in the system."""
    TRANSLATED_WORDS = 'TRANSLATED_WORDS'
    CORRECT_EXERCISES = 'CORRECT_EXERCISES'
    COMPLETED_AUDIO_LESSONS = 'COMPLETED_AUDIO_LESSONS'
    STREAK_DAYS = 'STREAK_DAYS'
    LEARNED_WORDS = 'LEARNED_WORDS'
    READ_ARTICLES = 'READ_ARTICLES'
    FRIENDS = 'FRIENDS'


class AwardMechanism(enum.Enum):
    """Enum representing all available badge award mechanisms in the system."""
    COUNTER = 'COUNTER'  # Progress value can only go up, incrementally
    GAUGE = 'GAUGE'  # Progress value always reflects current state and might reset to 0
    ONE_TIME = 'ONE_TIME'  # These badges only have 1 level, and are either achieved once or not


class BadgeCategory(db.Model):
    """
       Represents a category of badge that can be earned.
       Each category can have multiple badge levels defined in Badge.
    """
    __tablename__ = "badge_category"

    id = db.Column(db.Integer, primary_key=True)
    metric = db.Column(db.Enum(ActivityMetric), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    award_mechanism = db.Column(db.Enum(AwardMechanism), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("metric"),
    )

    badges = db.relationship("Badge", back_populates="badge_category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BadgeCategory {self.name}>"

    @classmethod
    def find(cls, metric: ActivityMetric) -> "BadgeCategory":
        """
        Find a badge category by its ActivityMetric enum value.

        Returns:
            BadgeCategory object if found, else None.
        """
        return cls.query.filter_by(metric=metric).first()
