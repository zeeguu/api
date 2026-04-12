from zeeguu.core.model.db import db


class Badge(db.Model):
    """
       Represents a specific badge level within an activity type.
       Each badge belongs to an ActivityType and has a level and threshold.
    """
    __tablename__ = "badge"

    id = db.Column(db.Integer, primary_key=True)
    activity_type_id = db.Column(db.Integer, db.ForeignKey("activity_type.id"), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    threshold = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100))
    icon_name = db.Column(db.String(255))

    __table_args__ = (
        db.UniqueConstraint("activity_type_id", "level"),
    )

    activity_type = db.relationship("ActivityType", back_populates="badges")
    user_badges = db.relationship(
        "UserBadge",
        back_populates="badge",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Badge ActivityType:{self.activity_type_id} Level:{self.level}>"

    @classmethod
    def find_all_achievable(cls, activity_type_id: int, current_value: int) -> list["Badge"]:
        """
        Find all badge levels for a specific activity type that are achievable
        given the user's current value.

        Returns:
            List of Badge objects that are achievable.
        """
        return cls.query.filter(
            cls.activity_type_id == activity_type_id,
            cls.threshold <= current_value
        ).all()

    @classmethod
    def find(cls, activity_type_id: int, level: int) -> "Badge | None":
        """
        Find a specific badge by activity type ID and level number.

        Returns:
            Badge object if found, else None.
        """
        return cls.query.filter_by(activity_type_id=activity_type_id, level=level).first()
