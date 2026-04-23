import random
from typing import Optional

from zeeguu.core.model.db import db



class UserAvatar(db.Model):
    __tablename__ = "user_avatar"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    image_name = db.Column(db.String(100))
    character_color = db.Column(db.String(7))
    background_color = db.Column(db.String(7))
    # Colors for avatar character and background.
    AVATAR_CHARACTER_COLORS = ["#F6D110", "#f09000", "#EA2F14", "#6367FF", "#0D1A63", "#008BFF", "#005F02"]
    AVATAR_BACKGROUND_COLORS = ["#FFF9C7", "#ffe0b3", "#ffc3b3", "#C9BEFF", "#81A6C6", "#9CD5FF", "#BCD9A2"]

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
    def random_colors(cls):
        """Return a randomly paired (character_color, background_color) tuple."""
        idx = random.randrange(len(cls.AVATAR_CHARACTER_COLORS))
        return cls.AVATAR_CHARACTER_COLORS[idx], cls.AVATAR_BACKGROUND_COLORS[idx]

    @classmethod
    def find(cls, user_id: int) -> Optional["UserAvatar"]:
        """
        Return the corresponding avatar for the given user.
        """
        return cls.query.filter_by(user_id=user_id).one_or_none()

    @classmethod
    def update_or_create(cls, user_id, image_name, character_color, background_color):
        """
        Update an existing avatar or create a new one for the specified user.
        Does not commit.
        """
        user_avatar = cls.find(user_id)
        if user_avatar:
            user_avatar.image_name = image_name
            user_avatar.character_color = character_color
            user_avatar.background_color = background_color
        else:
            user_avatar = UserAvatar(user_id, image_name, character_color, background_color)
        return user_avatar
