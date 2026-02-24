from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    UnicodeText,
    desc,
    Enum,
    BigInteger,
)
from zeeguu.core.model.db import db

class Badge(db.Model):
    __tablename__ = "badge"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_hidden = db.Column(db.Boolean, default=False)

    # Relationships
    levels = db.relationship("BadgeLevel", back_populates="badge", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Badge {self.name}>"

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
    
class UserBadgeLevel(db.Model):
    __tablename__ = "user_badge_level"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    badge_level_id = db.Column(db.Integer, db.ForeignKey("badge_level.id"), nullable=False)
    achieved_at = db.Column(db.DateTime, default=None)
    shown_popup = db.Column(db.Boolean, default=False)

    # Constraints
    __table_args__ = (
        db.UniqueConstraint("user_id", "badge_level_id"),
    )

    # Relationships
    badge_level = db.relationship("BadgeLevel", back_populates="user_badge_levels")
    user = db.relationship("User")  # Assuming User model exists

    def __repr__(self):
        return f"<UserBadgeLevel User:{self.user_id} BadgeLevel:{self.badge_level_id}>"
    
    