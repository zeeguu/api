from zeeguu.core.model.db import db


class UserBadgeProgress(db.Model):
    """
        Tracks a user's current value for a specific activity type.
        Used to determine badge threshold eligibility.
    """
    __tablename__ = "user_badge_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    badge_category_id = db.Column(db.Integer, db.ForeignKey("badge_category.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "badge_category_id"),
    )

    badge_category = db.relationship("BadgeCategory")
    user = db.relationship("User")

    def __init__(
            self,
            user_id,
            badge_category_id,
            value=0
    ):
        self.user_id = user_id
        self.badge_category_id = badge_category_id
        self.value = value

    def __repr__(self):
        return f"<UserBadgeProgress User:{self.user_id} BadgeCategory:{self.badge_category_id} Value:{self.value}>"

    @classmethod
    def find_all(cls, user_id: int) -> list["UserBadgeProgress"]:
        """Return all metric records for a user."""
        return cls.query.filter_by(user_id=user_id).all()

    @classmethod
    def find(cls, user_id: int, badge_category_ids: list[int]) -> list["UserBadgeProgress"]:
        """Return metric records for the given activity type IDs."""
        if not badge_category_ids:
            return []
        return cls.query.filter(cls.user_id == user_id, cls.badge_category_id.in_(badge_category_ids)).all()

    @classmethod
    def _get_or_create(
            cls,
            session,
            user_id: int,
            badge_category_id: int,
    ) -> "UserBadgeProgress":
        """
        Internal helper to fetch existing metric or create a new one (value=0).
        Does not commit.
        """
        record = cls.query.filter_by(
            user_id=user_id,
            badge_category_id=badge_category_id
        ).one_or_none()

        if not record:
            record = cls(user_id=user_id, badge_category_id=badge_category_id, value=0)
            session.add(record)

        return record

    @classmethod
    def create_or_increment(
            cls,
            session,
            user_id: int,
            badge_category_id: int,
            increment: int
    ) -> "UserBadgeProgress":
        """
        Increment value by the given amount.
        """
        record = cls._get_or_create(session, user_id, badge_category_id)
        record.value += increment
        session.add(record)
        return record

    @classmethod
    def create_or_update(
            cls,
            session,
            user_id: int,
            badge_category_id: int,
            value: int
    ) -> "UserBadgeProgress":
        """
        Overwrite value with a new value.
        """
        record = cls._get_or_create(session, user_id, badge_category_id)
        record.value = value
        session.add(record)
        return record
