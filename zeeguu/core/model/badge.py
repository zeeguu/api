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


    

    
    