from zeeguu.core.model.db import db


class UserMetric(db.Model):
    """
        Tracks a user's current value for a specific activity type.
        Used to determine badge threshold eligibility.
    """
    __tablename__ = "user_metric"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    activity_type_id = db.Column(db.Integer, db.ForeignKey("activity_type.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "activity_type_id"),
    )

    activity_type = db.relationship("ActivityType")
    user = db.relationship("User")

    def __init__(
            self,
            user_id,
            activity_type_id,
            value=0
    ):
        self.user_id = user_id
        self.activity_type_id = activity_type_id
        self.value = value

    def __repr__(self):
        return f"<UserMetric User:{self.user_id} ActivityType:{self.activity_type_id} Value:{self.value}>"

    @classmethod
    def find_all(cls, user_id: int) -> list["UserMetric"]:
        """Return all metric records for a user."""
        return cls.query.filter_by(user_id=user_id).all()

    @classmethod
    def find(cls, user_id: int, activity_type_ids: list[int]) -> list["UserMetric"]:
        """Return metric records for the given activity type IDs."""
        if not activity_type_ids:
            return []
        return cls.query.filter(cls.user_id == user_id, cls.activity_type_id.in_(activity_type_ids)).all()

    @classmethod
    def _get_or_create(
            cls,
            session,
            user_id: int,
            activity_type_id: int,
    ) -> "UserMetric":
        """
        Internal helper to fetch existing metric or create a new one (value=0).
        Does not commit.
        """
        record = cls.query.filter_by(
            user_id=user_id,
            activity_type_id=activity_type_id
        ).one_or_none()

        if not record:
            record = cls(user_id=user_id, activity_type_id=activity_type_id, value=0)
            session.add(record)

        return record

    @classmethod
    def create_or_increment(
            cls,
            session,
            user_id: int,
            activity_type_id: int,
            increment: int
    ) -> "UserMetric":
        """
        Increment value by the given amount.
        """
        record = cls._get_or_create(session, user_id, activity_type_id)
        record.value += increment
        session.add(record)
        return record

    @classmethod
    def create_or_update(
            cls,
            session,
            user_id: int,
            activity_type_id: int,
            value: int
    ) -> "UserMetric":
        """
        Overwrite value with a new value.
        """
        record = cls._get_or_create(session, user_id, activity_type_id)
        record.value = value
        session.add(record)
        return record
