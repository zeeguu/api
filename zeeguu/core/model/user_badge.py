from zeeguu.core.model import db

class UserBadge(db.Model):
    __tablename__ = "user_badge"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badge.id"), nullable=False)
    achieved_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=True)
    shown_popup = db.Column(db.Boolean, default=False)

    # Relationships
    user = db.relationship("User", backref="user_badges")
    badge = db.relationship("Badge", backref="user_badges")

    __table_args__ = (
        db.UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),
    )

    def __repr__(self):
        return f"<UserBadge user={self.user_id} badge={self.badge_id}>"

