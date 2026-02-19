from zeeguu.core.model import db

class Badge(db.Model):
    __tablename__ = "badge"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon_url = db.Column(db.String(255))
    tier = db.Column(
        db.Enum("bronze", "silver", "gold", "platinum", name="badge_tier"),
        nullable=False
    )
    is_hidden = db.Column(db.Boolean, default=False)
    is_unique = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Badge {self.name} (Tier: {self.tier})>"

