from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, ForeignKey, func, or_, case
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.user_avatar import UserAvatar


class Friendship(db.Model):
    __tablename__ = "friendship"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    # The user ids are stored in a consistent order (smaller id first) to simplify queries
    user_a_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user_b_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    deleted_at = Column(DateTime, nullable=True)
    friend_streak = Column(Integer, default=0)  # Tracks streak with this friend
    friend_streak_last_updated = Column(DateTime, nullable=True)

    user_a = relationship(
        User,
        foreign_keys=[user_a_id],
        primaryjoin="Friendship.user_a_id == User.id"
    )
    user_b = relationship(
        User,
        foreign_keys=[user_b_id],
        primaryjoin="Friendship.user_b_id == User.id"
    )

    def __init__(self, user_a_id: int, user_b_id: int):
        # Always store in canonical order (smaller id first) so every query
        # can use a simple or_ without worrying about which side is which.
        if user_a_id > user_b_id:
            user_a_id, user_b_id = user_b_id, user_a_id
        self.user_a_id = user_a_id
        self.user_b_id = user_b_id

    @classmethod
    def get_friend_objects(cls, user_id):
        """Return all Friend objects (including soft-deleted) associated with the given user_id."""
        friends = (
            cls.query
            .filter(or_(cls.user_a_id == user_id, cls.user_b_id == user_id))
            .all()
        )
        return friends

    @classmethod
    def get_friendship_map(cls, user_id: int) -> dict:
        """Return a dict mapping each friend's user id to their Friend object with user_id."""
        friendships = (
            cls.query
            .filter(or_(cls.user_a_id == user_id, cls.user_b_id == user_id))
            .filter(cls.deleted_at.is_(None))
            .all()
        )
        return {
            (f.user_b_id if f.user_a_id == user_id else f.user_a_id): f
            for f in friendships
        }

    @classmethod
    def get_friends_of(cls, user_id: int):
        """
        Return a list of all friends of the given user_id along with related data.

        Returns a list of dictionaries, each representing a friendship containing:
          - "user": the User object representing the friend
          - "friendship": the Friendship object linking the two users
          - "user_avatar": the UserAvatar object for the friend (or None if not set)
          - "user_languages": the list of active language of the friend (a list of
            UserLanguage objects)
        """
        from zeeguu.core.model import UserLanguage

        # Each friendship row stores both user ids but doesn't tell us which one
        # is "the other person" relative to the caller. The CASE expression derives
        # that at query time: if user_a_id is the caller, the other user is user_b_id,
        # and vice versa. This lets us do a single join to User instead of the
        # OR-of-ANDs pattern that would otherwise be required.
        other_user_id = case((cls.user_a_id == user_id, cls.user_b_id), else_=cls.user_a_id)
        rows = (
            db.session.query(User, cls, UserAvatar, UserLanguage)
            .select_from(cls)
            .filter(or_(cls.user_a_id == user_id, cls.user_b_id == user_id))
            .filter(cls.deleted_at.is_(None))
            .join(User, User.id == other_user_id)
            .outerjoin(UserAvatar, UserAvatar.user_id == User.id)
            .outerjoin(UserLanguage, UserLanguage.user_id == User.id)
            .all()
        )

        grouped = {}
        for user, friendship, avatar, language in rows:
            key = friendship.id

            if key not in grouped:
                grouped[key] = {
                    "user": user,
                    "friendship": friendship,
                    "user_avatar": avatar,
                    "user_languages": []
                }

            if language:
                grouped[key]["user_languages"].append(language)

        return list(grouped.values())

    @classmethod
    def are_friends(cls, user_1_id: int, user_2_id: int) -> bool:
        """Return True if two users are friends (in either direction)."""
        if user_1_id is None or user_2_id is None:
            return False

        if user_1_id == user_2_id:
            return True # You are always a friend to yourself

        a_id, b_id = min(user_1_id, user_2_id), max(user_1_id, user_2_id)
        friendship = (
            cls.query
            .filter(cls.user_a_id == a_id, cls.user_b_id == b_id)
            .filter(cls.deleted_at.is_(None))
            .first()
        )
        return friendship is not None

    @classmethod
    def remove(cls, user_1_id: int, user_2_id: int) -> bool:
        """
        Deletes a friendship between two users.

        Only does a logical delete by setting deleted_at to the current time.
        """
        a_id, b_id = min(user_1_id, user_2_id), max(user_1_id, user_2_id)
        friendship = (
            cls.query
            .filter(cls.user_a_id == a_id, cls.user_b_id == b_id)
            .filter(cls.deleted_at.is_(None))
            .first()
        )

        if friendship:
            friendship.deleted_at = datetime.now()
            db.session.add(friendship)
            db.session.flush()

            from zeeguu.core import events
            events.friendship_changed.send(None, user_id=user_1_id, db_session=db.session)
            events.friendship_changed.send(None, user_id=user_2_id, db_session=db.session)
            db.session.commit()

            return True

        return False

    @classmethod
    def find_friend_details(cls, user_id: int, friend_username: str):
        """
        Fetch profile details of the given friend_username.

        Returns the target user and additional information including:
            - target user's avatar
            - friendship between user_id and friend_username, if exists,
            - or friend request between user_id and friend_username, if exists.
        Returns None if the target user is not found.
        """
        from zeeguu.core.model.user import User
        from zeeguu.core.model.friend_request import FriendRequest

        friend_user: User = User.find_by_username(friend_username)
        if friend_user is None:
            return None
        friend_user_id = friend_user.id

        friend_user_avatar = UserAvatar.find(friend_user_id)

        a_id, b_id = min(user_id, friend_user_id), max(user_id, friend_user_id)
        friendship = (
            cls.query
            .filter(cls.user_a_id == a_id, cls.user_b_id == b_id)
            .filter(cls.deleted_at.is_(None))
            .first()
        )

        friend_request = FriendRequest.query.filter(
            ((FriendRequest.sender_id == user_id) & (FriendRequest.receiver_id == friend_user_id)) |
            ((FriendRequest.sender_id == friend_user_id) & (FriendRequest.receiver_id == user_id))
        ).order_by(FriendRequest.created_at.desc()).first()

        return friend_user, friend_user_avatar, friendship, friend_request

    @classmethod
    def add(cls, user_id: int, other_id: int):
        """
        Creates a friendship between two users, or returns it if they are already friends.

        If their friendship was previously logically deleted, this will create a new
        row for the same users instead of overwriting the existing one. This ensures
        past friend leaderboards will show correct data for their respective time periods.
        """
        # Ensure canonical ordering before any lookup or insert
        if user_id > other_id:
            # This swaps the values of user_id and other_id so that user_id is always the smaller one
            user_id, other_id = other_id, user_id

        # Check if friendship already exists
        existing = (
            cls.query
            .filter(cls.user_a_id == user_id, cls.user_b_id == other_id)
            .filter(cls.deleted_at.is_(None))
            .first()
        )

        if existing:
            return existing  # friendship already exists

        # Add friendship
        friendship = Friendship(user_a_id=user_id, user_b_id=other_id)
        db.session.add(friendship)
        db.session.flush()

        from zeeguu.core import events
        events.friendship_changed.send(None, user_id=user_id, db_session=db.session)
        events.friendship_changed.send(None, user_id=other_id, db_session=db.session)
        db.session.commit()

        return friendship

    @classmethod
    def count_active_friends(cls, user_id: int, db_session) -> int:
        """Return the current number of friends for a user."""
        return (
                db_session.query(func.count(cls.id))
                .filter(
                    ((cls.user_a_id == user_id) | (cls.user_b_id == user_id)),
                    cls.deleted_at.is_(None),
                )
                .scalar()
                or 0
        )
