from zeeguu.core.model.db import db


class Badge(db.Model):
    """
       Represents a specific badge level within a badge category.
       Each badge belongs to an BadgeCategory and has a level and threshold.
    """
    __tablename__ = "badge"

    id = db.Column(db.Integer, primary_key=True)
    badge_category_id = db.Column(db.Integer, db.ForeignKey("badge_category.id"), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    threshold = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100))
    description = db.Column(db.Text)
    icon_name = db.Column(db.String(255))

    __table_args__ = (
        db.UniqueConstraint("badge_category_id", "level"),
    )

    badge_category = db.relationship("BadgeCategory", back_populates="badges")
    user_badges = db.relationship(
        "UserBadge",
        back_populates="badge"
    )

    def __repr__(self):
        return f"<Badge BadgeCategory:{self.badge_category_id} Level:{self.level}>"
