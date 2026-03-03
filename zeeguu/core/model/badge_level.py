from zeeguu.core.model.db import db


class BadgeLevel(db.Model):
    """
        Represents a level of a badge. Each badge can have multiple levels, each
        with a target value and optional icon. Levels are unique per badge.
    """
    __tablename__ = "badge_level"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    badge_id = db.Column(db.Integer, db.ForeignKey("badge.id"), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    target_value = db.Column(db.Integer, nullable=False)
    icon_url = db.Column(db.String(255))

    __table_args__ = (
        db.UniqueConstraint("badge_id", "level"),
    )

    badge = db.relationship("Badge", back_populates="badge_levels")
    user_badge_levels = db.relationship(
        "UserBadgeLevel",
        back_populates="badge_level",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<BadgeLevel Badge:{self.badge_id} Level:{self.level}>"

    @classmethod
    def find_all_achievable(cls, badge_id: int, current_value: int) -> list["BadgeLevel"]:
        """
        Find all badge levels for a specific badge that the user can achieve given their current value.

        Args:
            badge_id: The ID of the badge.
            current_value: The user's current value for the badge metric.

        Returns:
            List of BadgeLevel objects that are achievable.
        """
        return cls.query.filter(
            cls.badge_id == badge_id,
            cls.target_value <= current_value
        ).all()

    @classmethod
    def find(cls, badge_id: int, level: int) -> "BadgeLevel | None":
        """
        Find a specific badge level by badge ID and level number.

        Args:
            badge_id: The ID of the badge.
            level: The level number.

        Returns:
            BadgeLevel object if found, else None.
        """
        return cls.query.filter_by(badge_id=badge_id, level=level).first()
