from zeeguu.core.model.db import db


class BadgeLevel(db.Model):
    __tablename__ = "badge_level"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    badge_id = db.Column(db.Integer, db.ForeignKey("badge.id"), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    target_value = db.Column(db.Integer, nullable=False)
    icon_url = db.Column(db.String(255))

    # Constraints
    __table_args__ = (
        db.UniqueConstraint("badge_id", "level"),
    )

    # Relationships
    badge = db.relationship("Badge", back_populates="badge_levels")
    user_badge_levels = db.relationship("UserBadgeLevel", back_populates="badge_level", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BadgeLevel Badge:{self.badge_id} Level:{self.level}>"

    @classmethod
    def find_all_achievable(cls, badge_id: int, current_value: int) -> list["BadgeLevel"]:
        """Find all badge levels for a specific badge id that are achievable"""
        return cls.query.filter(
            cls.badge_id == badge_id,
            cls.target_value <= current_value
        ).all()

    @classmethod
    def find(cls, badge_id: int, level: int) -> "BadgeLevel | None":
        """Find badge level for a specific badge id and level"""
        return cls.query.filter_by(badge_id=badge_id, level=level).first()
