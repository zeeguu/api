import enum

from zeeguu.core.model.db import db


class ActivityTypeMetric(enum.Enum):
    """Enum representing all available activity metrics in the system."""
    TRANSLATED_WORDS = 'TRANSLATED_WORDS'
    CORRECT_EXERCISES = 'CORRECT_EXERCISES'
    COMPLETED_AUDIO_LESSONS = 'COMPLETED_AUDIO_LESSONS'
    STREAK_COUNT = 'STREAK_COUNT'
    LEARNED_WORDS = 'LEARNED_WORDS'
    READ_ARTICLES = 'READ_ARTICLES'
    NUMBER_OF_FRIENDS = 'NUMBER_OF_FRIENDS'


class BadgeType(enum.Enum):
    """Enum representing all available badge types in the system."""
    COUNTER = 'COUNTER'  # Progress value can only go up, incrementally
    GAUGE = 'GAUGE'  # Progress value always reflects current state and might reset to 0
    ONE_TIME = 'ONE_TIME'  # These badges only have 1 level, and are either achieved once or not


class ActivityType(db.Model):
    """
       Represents a type of activity that can earn badges. Each activity type
       can have multiple badge levels defined in Badge.
    """
    __tablename__ = "activity_type"

    id = db.Column(db.Integer, primary_key=True)
    metric = db.Column(db.Enum(ActivityTypeMetric), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    badge_type = db.Column(db.Enum(BadgeType), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("metric"),
    )

    badges = db.relationship("Badge", back_populates="activity_type", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ActivityType {self.name}>"

    @classmethod
    def find(cls, metric: ActivityTypeMetric) -> "ActivityType":
        """
        Find an activity type by its ActivityTypeMetric enum value.

        Returns:
            ActivityType object if found, else None.
        """
        return cls.query.filter_by(metric=metric).first()
