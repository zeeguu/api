from typing import Optional

from zeeguu.core.model.db import db


class UserAvatar(db.Model):
    """

    """
    __tablename__ = "user_avatar"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    image_name = db.Column(db.String(100))
    character_color = db.Column(db.String(7))
    background_color = db.Column(db.String(7))

    user = db.relationship("User")

    def __init__(
            self,
            user_id,
            image_name=None,
            character_color=None,
            background_color=None
    ):
        self.user_id = user_id
        self.image_name = image_name
        self.character_color = character_color
        self.background_color = background_color

    def __repr__(self):
        return f"<UserAvatar User:{self.user_id}>"

    @classmethod
    def find(cls, user_id: int) -> Optional["UserAvatar"]:
        """Return the corresponding avatar for the given user."""
        return cls.query.filter_by(user_id=user_id).one_or_none()
