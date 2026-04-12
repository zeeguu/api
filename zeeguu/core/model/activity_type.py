import enum

from zeeguu.core.model.db import db


class MetricKey(enum.Enum):
    """Enum representing all available activity metric keys in the system."""
    TRANSLATED_WORDS = 'TRANSLATED_WORDS'
    CORRECT_EXERCISES = 'CORRECT_EXERCISES'
    COMPLETED_AUDIO_LESSONS = 'COMPLETED_AUDIO_LESSONS'
    STREAK_COUNT = 'STREAK_COUNT'
    LEARNED_WORDS = 'LEARNED_WORDS'
    READ_ARTICLES = 'READ_ARTICLES'
    NUMBER_OF_FRIENDS = 'NUMBER_OF_FRIENDS'


class ActivityType(db.Model):
    """
       Represents a type of activity that can earn badges. Each activity type
       can have multiple badge levels defined in Badge.
    """
    __tablename__ = "activity_type"

    id = db.Column(db.Integer, primary_key=True)
    metric_key = db.Column(db.Enum(MetricKey), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_accumulative = db.Column(db.Boolean)

    __table_args__ = (
        db.UniqueConstraint("metric_key"),
    )

    badges = db.relationship("Badge", back_populates="activity_type", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ActivityType {self.name}>"

    @classmethod
    def find(cls, metric_key: MetricKey) -> "ActivityType":
        """
        Find an activity type by its MetricKey enum value.

        Returns:
            ActivityType object if found, else None.
        """
        return cls.query.filter_by(metric_key=metric_key).first()
