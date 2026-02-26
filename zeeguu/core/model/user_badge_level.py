from datetime import datetime

import sqlalchemy
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db


class UserBadgeLevel(db.Model):
    __tablename__ = "user_badge_level"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    badge_level_id = db.Column(db.Integer, db.ForeignKey("badge_level.id"), nullable=False)
    achieved_at = db.Column(db.DateTime, default=None)
    is_shown = db.Column(db.Boolean, default=False)

    # Constraints
    __table_args__ = (
        db.UniqueConstraint("user_id", "badge_level_id"),
    )

    # Relationships
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
        if achieved_at is None:
            self.achieved_at = datetime.now()
        else:
            self.achieved_at = achieved_at

    def __repr__(self):
        return f"<UserBadgeLevel User:{self.user_id} {self.id} BadgeLevel:{self.badge_level_id}>"

    @classmethod
    def find_all(cls, user_id: int):
        """Find existing user badge levels by user id."""
        try:
            return cls.query.filter_by(user_id=user_id).all()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_all_not_shown(cls, user_id: int):
        """Find existing not shown user badge levels by user id."""
        try:
            return cls.query.filter_by(user_id=user_id, is_shown=False).all()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find(cls, user_id: int, badge_level_ids: list[int]):
        """Find user badge levels for a specific user_id and a list of badge_level_ids."""
        return cls.query.filter(cls.user_id == user_id, cls.badge_level_id.in_(badge_level_ids)).all()

    @classmethod
    def create(
            cls,
            session,
            user_id: int,
            badge_level_id: int,
            achieved_at: datetime = None,
            is_shown: bool = False,
    ):
        new = cls(user_id, badge_level_id, achieved_at, is_shown)
        session.add(new)
        session.commit()
        return new
