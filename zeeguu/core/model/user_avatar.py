from typing import Optional
import re

from zeeguu.core.model import User
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

    @classmethod
    def create_default_avatar_for_user(cls, user: User) -> "UserAvatar":
        """
        Return the existing avatar for the given user, if it exists.
        Otherwise, create a default avatar based on the user's username.

        The default avatar's image_name is derived from the part of the username
        after the first underscore, stripping any digits. If the result is empty
        or not in User.ANIMALS, the first animal from User.ANIMALS is used.

        Args:
            user (User): The user for whom to create or fetch the avatar.

        Returns:
            UserAvatar: The existing or newly created default avatar.
        """
        existing_avatar = cls.find(user.id)
        if existing_avatar:
            return existing_avatar

        _, _, tail = user.username.partition("_")
        animal_name = re.sub(r"\d+", "", tail)

        if not animal_name or animal_name not in User.ANIMALS:
            animal_name = User.ANIMALS[0]

        return UserAvatar(user.id, animal_name, None, None)
