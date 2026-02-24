from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db

class BadgeLevel(db.Model):
    __tablename__ = "badge_level"

    id = db.Column(db.Integer, primary_key=True)
    badge_id = db.Column(db.Integer, db.ForeignKey("badge.id"), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    target_value = db.Column(db.Integer, nullable=False)
    icon_url = db.Column(db.String(255))

    # Constraints
    __table_args__ = (
        db.UniqueConstraint("badge_id", "level"),
    )

    # Relationships
    badge = db.relationship("Badge", back_populates="levels")
    user_badge_levels = db.relationship("UserBadgeLevel", back_populates="badge_level", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BadgeLevel Badge:{self.badge_id} Level:{self.level}>"

    @classmethod
    def find(cls, badge_id: int, level: int):
        """Find badge level for a specific badge id and level"""
        return cls.query.filter_by(badge_id=badge_id, level = level).first()