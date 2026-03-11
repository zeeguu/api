from datetime import datetime

from zeeguu.core.model.db import db


class UserBadgeLevel(db.Model):
    """
        Represents the association between a user and a badge level they have achieved.
        Tracks when the badge level was achieved and whether it has been shown to the user.
    """
    __tablename__ = "user_badge_level"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    badge_level_id = db.Column(db.Integer, db.ForeignKey("badge_level.id"), nullable=False)
    achieved_at = db.Column(db.DateTime, default=datetime.now)
    is_shown = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "badge_level_id"),
    )

    badge_level = db.relationship("BadgeLevel", back_populates="user_badge_levels")
    user = db.relationship("User")

    def __init__(
            self,
            user_id,
            badge_level_id,
            achieved_at=None,
            is_shown=False
    ):
        self.user_id = user_id
        self.badge_level_id = badge_level_id
        self.is_shown = is_shown
        self.achieved_at = achieved_at or datetime.now()

    def __repr__(self):
        return f"<UserBadgeLevel User:{self.user_id} BadgeLevel:{self.badge_level_id}>"

    @classmethod
    def find_all(cls, user_id: int) -> list["UserBadgeLevel"]:
        """Return all badge levels achieved by a user."""
        return cls.query.filter_by(user_id=user_id).all()

    @classmethod
    def count_user_not_shown(cls, user_id: int) -> int:
        """Return the count of badge levels that the user has not seen yet."""
        return cls.query.filter_by(user_id=user_id, is_shown=False).count()

    @classmethod
    def find(cls, user_id: int, badge_level_ids: list[int]) -> list["UserBadgeLevel"]:
        """Return user badge levels for the specified badge_level_ids."""
        if not badge_level_ids:
            return []
        return cls.query.filter(cls.user_id == user_id, cls.badge_level_id.in_(badge_level_ids)).all()

    @classmethod
    def update_not_shown_for_user(cls, session, user_id: int):
        """
            Mark all badge levels for a user as shown.
            Does not commit.
        """
        unseen_levels = cls.query.filter_by(user_id=user_id, is_shown=False).all()
        for level in unseen_levels:
            level.is_shown = True
            session.add(level)

    @classmethod
    def create(
            cls,
            session,
            user_id: int,
            badge_level_id: int,
            achieved_at: datetime = None,
            is_shown: bool = False,
    ) -> "UserBadgeLevel":
        """
           Create a new UserBadgeLevel record for a user and badge level.
           Does not commit.
        """
        new = cls(user_id, badge_level_id, achieved_at, is_shown)
        session.add(new)
        return new
