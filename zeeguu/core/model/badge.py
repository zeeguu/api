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
    description = db.Column(db.Text)
    icon_name = db.Column(db.String(255))

    __table_args__ = (
        db.UniqueConstraint("activity_type_id", "level"),
    )

    activity_type = db.relationship("ActivityType", back_populates="badges")
    user_badges = db.relationship(
        "UserBadge",
        back_populates="badge"
    )

    def __repr__(self):
        return f"<Badge ActivityType:{self.activity_type_id} Level:{self.level}>"
