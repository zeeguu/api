from datetime import datetime

from zeeguu.core.model.db import db


class UserBadge(db.Model):
    """
        Represents the association between a user and a badge they have achieved.
        Tracks when the badge was achieved and whether it has been shown to the user.
    """
    __tablename__ = "user_badge"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badge.id"), nullable=False)
    achieved_at = db.Column(db.DateTime, default=datetime.now)
    is_shown = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "badge_id"),
    )

    badge = db.relationship("Badge", back_populates="user_badges")
    user = db.relationship("User", back_populates="badges")

    def __init__(
            self,
            user_id,
            badge_id,
            achieved_at=None,
            is_shown=False
    ):
        self.user_id = user_id
        self.badge_id = badge_id
        self.is_shown = is_shown
        self.achieved_at = achieved_at or datetime.now()

    def __repr__(self):
        return f"<UserBadge User:{self.user_id} Badge:{self.badge_id}>"

    @classmethod
    def find_all(cls, user_id: int) -> list["UserBadge"]:
        """Return all badges achieved by a user."""
        return cls.query.filter_by(user_id=user_id).all()

    @classmethod
    def count_user_not_shown(cls, user_id: int) -> int:
        """Return the count of badges that the user has not seen yet."""
        return cls.query.filter_by(user_id=user_id, is_shown=False).count()

    @classmethod
    def find(cls, user_id: int, badge_ids: list[int]) -> list["UserBadge"]:
        """Return user badges for the specified badge_ids."""
        if not badge_ids:
            return []
        return cls.query.filter(cls.user_id == user_id, cls.badge_id.in_(badge_ids)).all()

    @classmethod
    def update_not_shown_for_user(cls, session, user_id: int):
        """
            Mark all badges for a user as shown.
            Does not commit.
        """
        unseen = cls.query.filter_by(user_id=user_id, is_shown=False).all()
        for badge in unseen:
            badge.is_shown = True
            session.add(badge)

    @classmethod
    def create(
            cls,
            session,
            user_id: int,
            badge_id: int,
            achieved_at: datetime = None,
            is_shown: bool = False,
    ) -> "UserBadge":
        """
           Create a new UserBadge record for a user and badge.
           Does not commit.
        """
        new = cls(user_id, badge_id, achieved_at, is_shown)
        session.add(new)
        return new
