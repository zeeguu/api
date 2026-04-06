from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, DateTime, ForeignKey, func, or_, and_
from sqlalchemy.orm import relationship, object_session

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.user_avatar import UserAvatar


class Friend(db.Model):
    __tablename__ = "friend"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    friend_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    deleted_at = Column(DateTime, nullable=True)
    friend_streak = Column(Integer, default=0)  # Tracks streak with this friend
    friend_streak_last_updated = Column(DateTime, nullable=True)

    user = relationship(
        User,
        foreign_keys=[user_id],
        primaryjoin="Friend.user_id == User.id"
    )
    friend = relationship(
        User,
        foreign_keys=[friend_id],
        primaryjoin="Friend.friend_id == User.id"
    )

    def update_friend_streak(self, session=None, commit=True):
        """
        Update friend_streak based on both users' most recent practice in any language.
        Uses the latest last_practiced date across all UserLanguage records for each user.
        """
        from zeeguu.core.model.user_language import UserLanguage

        session = session or object_session(self) or db.session

        # Get all UserLanguage records for each user
        user_langs = UserLanguage.query.filter(UserLanguage.user_id == self.user_id).all()
        friend_langs = UserLanguage.query.filter(UserLanguage.user_id == self.friend_id).all()

        # Find the most recent last_practiced date for each user
        user_date = None
        friend_date = None
        if user_langs:
            user_date = max((ul.last_practiced for ul in user_langs if ul.last_practiced), default=None)
        if friend_langs:
            friend_date = max((ul.last_practiced for ul in friend_langs if ul.last_practiced), default=None)

        user_date = user_date.date() if user_date else None
        friend_date = friend_date.date() if friend_date else None
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        last_updated_date = (
            self.friend_streak_last_updated.date()
            if self.friend_streak_last_updated
            else None
        )

        # If both practiced today, update at most once per day.
        if user_date == today and friend_date == today:
            if last_updated_date != today:
                if last_updated_date == yesterday and (self.friend_streak or 0) > 0:
                    self.friend_streak = (self.friend_streak or 0) + 1
                else:
                    self.friend_streak = 1
                self.friend_streak_last_updated = datetime.now()
        # Do not reset if one side has never practiced yet.
        elif user_date is None or friend_date is None:
            pass
        # Reset only when at least one side has not practiced since before yesterday.
        elif user_date < yesterday or friend_date < yesterday:
            self.friend_streak = 0
            self.friend_streak_last_updated = datetime.now()

        if session:
            session.add(self)
            if commit:
                session.commit()

    @staticmethod
    def get_friends(user_id):
        """Return a list of User objects that are friends with the given user_id."""
        # query where user is either the user_id or the friend_id
        friends = (
            db.session.query(User)
            .join(
                Friend,
                ((Friend.user_id == user_id) & (Friend.friend_id == User.id)) |
                ((Friend.friend_id == user_id) & (Friend.user_id == User.id))
            )
            .filter(Friend.deleted_at.is_(None))
            .all()
        )
        return friends

    @staticmethod
    def get_friends_with_details(user_id: int):
        """
        Return a list of all friends of the given user_id along with related data.

        Returns a list of dictionaries, each representing a friendship containing:
          - "user": the User object representing the friend
          - "friendship": the Friend object linking the two users
          - "user_avatar": the UserAvatar object for the friend (or None if not set)
          - "user_languages": the list of active language of the friend (a list of
            UserLanguage objects)
        """
        from zeeguu.core.model import UserLanguage
        rows = (
            db.session.query(User, Friend, UserAvatar, UserLanguage)
            .select_from(User)
            .join(
                Friend,
                or_(
                    and_(Friend.user_id == user_id, Friend.friend_id == User.id),
                    and_(Friend.friend_id == user_id, Friend.user_id == User.id),
                )
            )
            .outerjoin(UserAvatar, UserAvatar.user_id == User.id)
            .outerjoin(UserLanguage, UserLanguage.user_id == User.id)
            .filter(Friend.deleted_at.is_(None))
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
    def are_friends(cls, user1_id: int, user2_id: int) -> bool:
        """Return True if two users are friends (in either direction)."""
        if user1_id is None or user2_id is None:
            return False

        if user1_id == user2_id:
            return True

        friendship = (
            cls.query
            .filter(
                ((cls.user_id == user1_id) & (cls.friend_id == user2_id)) |
                ((cls.user_id == user2_id) & (cls.friend_id == user1_id))
            )
            .filter(cls.deleted_at.is_(None))
            .first()
        )
        return friendship is not None

    @classmethod
    def remove_friendship(cls, user1_id: int, user2_id: int) -> bool:
        """
        Deletes a friendship between two users.

        Only does a logical delete by setting deleted_at to the current time.
        """
        # Look for friendship in either direction
        friendship = (
            cls.query
            .filter(
                ((cls.user_id == user1_id) & (cls.friend_id == user2_id)) |
                ((cls.user_id == user2_id) & (cls.friend_id == user1_id))
            )
            .filter(cls.deleted_at.is_(None))
            .first()
        )

        if friendship:
            friendship.deleted_at = datetime.now()
            db.session.add(friendship)
            db.session.commit()
            return True

        return False

    @classmethod
    def find_friend_details(cls, user_id: int, friend_username: str):
        """
        Fetch profile details of the given friend_username.

        Returns the target user's details_as_dictionary(), with additional
        information including:
        - friendship data (created_at, friend_streak, ...) between user_id
          and friend_username, if exists,
        - or friend request data (sender_username, receiver_username,
          friend_request_status ...) between user_id and friend_username,
          if exists.
        Returns None if the target user is not found.
        """
        from zeeguu.core.model.user import User
        from zeeguu.core.model.friend_request import FriendRequest

        friend = User.find_by_username(friend_username)
        if friend is None:
            return None
        friend_user_id = friend.id

        friendship = (
            cls.query
            .filter(
                ((cls.user_id == user_id) & (cls.friend_id == friend_user_id)) |
                ((cls.user_id == friend_user_id) & (cls.friend_id == user_id))
            )
            .filter(cls.deleted_at.is_(None))
            .first()
        )

        friend_request = FriendRequest.query.filter(
            ((FriendRequest.sender_id == user_id) & (FriendRequest.receiver_id == friend_user_id)) |
            ((FriendRequest.sender_id == friend_user_id) & (FriendRequest.receiver_id == user_id))
        ).order_by(FriendRequest.created_at.desc()).first()

        details = friend.details_as_dictionary()
        details["friendship"] = cls._get_friendship_or_friend_request(friendship, friend_request)

        if friendship:
            details["friends_since"] = friendship.created_at.isoformat() if friendship.created_at else None
            details["mutual_streak"] = friendship.friend_streak or 0

        return details

    @classmethod
    def search_users(cls, current_user_id: int, term: str, limit: int = 20):
        """
        Search users by username (partial match) or exact email or name.
        For each user, return:
            - user info
            - friendship status (if any)
            - friend request status (if any)
        """
        from sqlalchemy import or_, func
        from zeeguu.core.model.friend_request import FriendRequest

        filters = []
        term = term.lower()
        if term:
            filters.append(func.lower(User.username).ilike(f"%{term}%"))  # case-insensitive partial match for username
            filters.append(func.lower(User.email) == term)  # exact match for email
            filters.append(func.lower(User.name) == term)  # exact match for name

        if not filters:
            return []  # nothing to search

        query = (
            db.session.query(User, UserAvatar)
            .select_from(User)
            .filter(
                or_(*filters),
                User.id != current_user_id
            )
            .outerjoin(UserAvatar, UserAvatar.user_id == User.id)
            .limit(limit)
        )

        # Fetch all friendships involving the current user
        friendships = (
            Friend.query
            .filter(
                (Friend.user_id == current_user_id) | (Friend.friend_id == current_user_id)
            )
            .filter(Friend.deleted_at.is_(None))
            .all()
        )

        friendship_map = {}
        for friendship in friendships:
            other_id = friendship.friend_id if friendship.user_id == current_user_id else friendship.user_id
            friendship_map[other_id] = friendship

        # Fetch all friend requests involving the current user
        friend_requests = FriendRequest.query.filter(
            (FriendRequest.sender_id == current_user_id) | (FriendRequest.receiver_id == current_user_id)
        ).all()

        friend_request_map = {}
        for friend_request in friend_requests:
            other_id = friend_request.receiver_id if friend_request.sender_id == current_user_id else friend_request.sender_id
            friend_request_map[other_id] = friend_request

        results = []

        for user, avatar in query.all():
            results.append({
                "user": user,
                "user_avatar": avatar,
                "friendship": friendship_map.get(user.id),
                "friend_request": friend_request_map.get(user.id),
            })

        return results

    @staticmethod
    def add_friendship(user_id: int, friend_id: int):
        """
        Creates a friendship between two users, or returns it if they are already friends.

        If their friendship was previously logically deleted, this will create a new
        row for the same users instead of overwriting the existing one. This ensures
        past friend leaderboards will show correct data for their respective time periods.
        """
        # Check if friendship already exists
        existing = (
            Friend.query
            .filter(
                ((Friend.user_id == user_id) & (Friend.friend_id == friend_id)) |
                ((Friend.user_id == friend_id) & (Friend.friend_id == user_id))
            )
            .filter(Friend.deleted_at.is_(None))
            .first()
        )

        if existing:
            return existing  # friendship already exists

        # Add friendship
        friendship = Friend(user_id=user_id, friend_id=friend_id)
        db.session.add(friendship)
        db.session.commit()
        db.session.refresh(friendship)
        return friendship

    @staticmethod
    def _get_friendship_or_friend_request(friendship, friend_request):
        if friendship:
            return {
                "friend_streak": friendship.friend_streak,
                "friend_streak_last_updated": (
                    friendship.friend_streak_last_updated.isoformat()
                    if friendship.friend_streak_last_updated
                    else None
                ),
                "friend_request_status": "accepted",
                "created_at": friendship.created_at.isoformat() if friendship.created_at else None,
            }
        elif friend_request:
            return {
                "sender_username": friend_request.sender.username,
                "receiver_username": friend_request.receiver.username,
                "friend_streak": 0,
                "friend_streak_last_updated": None,
                "friend_request_status": friend_request.status,
                "created_at": (
                    friend_request.created_at.isoformat()
                    if friend_request.created_at
                    else None
                ),
            }
