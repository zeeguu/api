from zeeguu.core.model.db import db


class UserBadgeProgress(db.Model):
    """
        Tracks a user's progress toward a specific badge.
        Stores the current metric value used to determine badge level eligibility.
    """
    __tablename__ = "user_badge_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badge.id"), nullable=False)
    current_value = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "badge_id"),
    )

    badge = db.relationship("Badge")
    user = db.relationship("User")

    def __init__(
            self,
            user_id,
            badge_id,
            current_value=0
    ):
        self.user_id = user_id
        self.badge_id = badge_id
        self.current_value = current_value

    def __repr__(self):
        return f"<UserBadgeProgress User:{self.user_id} BadgeLevel:{self.badge_id} Value:{self.current_value}>"

    @classmethod
    def find_all(cls, user_id: int) -> list["UserBadgeProgress"]:
        """Return all badge progress records for a user."""
        return cls.query.filter_by(user_id=user_id).all()

    @classmethod
    def find(cls, user_id: int, badge_ids: list[int]) -> list["UserBadgeProgress"]:
        """Return progress records for the given badge IDs."""
        if not badge_ids:
            return []
        return cls.query.filter(cls.user_id == user_id, cls.badge_id.in_(badge_ids)).all()

    @classmethod
    def _get_or_create(
            cls,
            session,
            user_id: int,
            badge_id: int,
    ) -> "UserBadgeProgress":
        """
        Internal helper to fetch existing progress or create a new one (value=0).
        Does not commit.
        """
        record = cls.query.filter_by(
            user_id=user_id,
            badge_id=badge_id
        ).one_or_none()

        if not record:
            record = cls(user_id=user_id, badge_id=badge_id, current_value=0)
            session.add(record)

        return record

    @classmethod
    def create_or_increment(
            cls,
            session,
            user_id: int,
            badge_id: int,
            increment: int
    ) -> "UserBadgeProgress":
        """
        Increment current_value by the given amount.
        """
        record = cls._get_or_create(session, user_id, badge_id)
        record.current_value += increment
        session.add(record)
        return record

    @classmethod
    def create_or_update(
            cls,
            session,
            user_id: int,
            badge_id: int,
            value: int
    ) -> "UserBadgeProgress":
        """
        Overwrite current_value with a new value.
        """
        record = cls._get_or_create(session, user_id, badge_id)
        record.current_value = value
        session.add(record)
        return record
