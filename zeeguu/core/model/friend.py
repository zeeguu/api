from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, DateTime, ForeignKey, func, or_, case
from sqlalchemy.orm import relationship, object_session

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.model.user_avatar import UserAvatar


class Friend(db.Model):
    __tablename__ = "friend"
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
        primaryjoin="Friend.user_a_id == User.id"
    )
    user_b = relationship(
        User,
        foreign_keys=[user_b_id],
        primaryjoin="Friend.user_b_id == User.id"
    )

    def __init__(self, user_a_id: int, user_b_id: int):
        # Always store in canonical order (smaller id first) so every query
        # can use a simple or_ without worrying about which side is which.
        if user_a_id > user_b_id:
            user_a_id, user_b_id = user_b_id, user_a_id
        self.user_a_id = user_a_id
        self.user_b_id = user_b_id

    @property
    def current_friend_streak(self):
        """Stored friend streak, zeroed out if not updated today or yesterday."""
        last_updated = self.friend_streak_last_updated.date() if self.friend_streak_last_updated else None
        yesterday = datetime.now().date() - timedelta(days=1)

        if last_updated is None:
            return 0

        if last_updated < yesterday:
            return 0

        return self.friend_streak or 0

    def update_friend_streak(self, session=None, commit=True):
        """
        Update friend_streak based on both users' most recent practice in any language.
        Uses the latest last_practiced date across all UserLanguage records for each user.
        """
        from zeeguu.core.model.user_language import UserLanguage

        session = session or object_session(self) or db.session

        # Get all UserLanguage records for each user
        user_langs = UserLanguage.query.filter(UserLanguage.user_id == self.user_a_id).all()
        friend_langs = UserLanguage.query.filter(UserLanguage.user_id == self.user_b_id).all()

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

    @classmethod
    def get_friend_objects(cls, user_id):
        """Return all Friend objects (including soft-deleted) associated with the given user_id."""
        friends = (
            db.session.query(cls)
            .filter(or_(Friend.user_a_id == user_id, Friend.user_b_id == user_id))
            .all()
        )
        return friends

    @staticmethod
    def get_friend_users(user_id):
        """Return a list of User objects that are friends with the given user_id."""
        other_user_id = case((Friend.user_a_id == user_id, Friend.user_b_id), else_=Friend.user_a_id)
        friends = (
            db.session.query(User)
            .select_from(Friend)
            .filter(or_(Friend.user_a_id == user_id, Friend.user_b_id == user_id))
            .filter(Friend.deleted_at.is_(None))
            .join(User, User.id == other_user_id)
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

        # Each friendship row stores both user ids but doesn't tell us which one
        # is "the other person" relative to the caller. The CASE expression derives
        # that at query time: if user_a_id is the caller, the other user is user_b_id,
        # and vice versa. This lets us do a single join to User instead of the
        # OR-of-ANDs pattern that would otherwise be required.
        other_user_id = case((Friend.user_a_id == user_id, Friend.user_b_id), else_=Friend.user_a_id)
        rows = (
            db.session.query(User, Friend, UserAvatar, UserLanguage)
            .select_from(Friend)
            .filter(or_(Friend.user_a_id == user_id, Friend.user_b_id == user_id))
            .filter(Friend.deleted_at.is_(None))
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
    def remove_friendship(cls, user_1_id: int, user_2_id: int) -> bool:
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
            db.session.commit()

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

        Returns the target user's details_as_dictionary(), with additional
        information including:
        - friendship data (created_at, friend_streak, ...) between user_id
          and friend_username, if exists,
        - or friend request data (sender_username, receiver_username,...) between user_id and friend_username,
          if exists.
        Returns None if the target user is not found.
        """
        from zeeguu.core.model.user import User
        from zeeguu.core.model.friend_request import FriendRequest

        friend: User = User.find_by_username(friend_username)
        if friend is None:
            return None
        friend_user_id = friend.id

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

        details = friend.details_as_dictionary()
        details.pop("email", None) # Do not include email in friend details
        details["friendship"] = cls._get_friendship_or_friend_request(friendship, friend_request)

        if friendship:
            details["friends_since"] = friendship.created_at.isoformat() if friendship.created_at else None
            details["mutual_streak"] = friendship.current_friend_streak or 0

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
            # The 'like()' acts just as 'ilike()' here due to the utf8mb4_unicode_ci collation; the % characters allow for partial matches
            # The username, email and name are all utf8mb4_unicode_ci, so they are all case-insensitive.
            # NOTE: So there is no need to apply func.lower() to the column values here, as the collation handles that for us.
            # '%' and '_' are special in SQL LIKE patterns. A search for 100% becomes LIKE '%100%%'
            # The '%' from user input acts as a wildcard, matching 100percent, 100xyz, etc. 
            # Similarly, _ matches any single character. 
            # NOTE: We escape '\' first to avoid double-escaping, then escape '%' and '_' so they are treated as literal characters in the search term rather than wildcards.
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(User.username.like(f"%{escaped}%", escape="\\")) # case-insensitive partial match for username
            # The email column is only stored in lower case
            filters.append(User.name == term)  # exact match for name

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
            cls.query
            .filter(or_(cls.user_a_id == current_user_id, cls.user_b_id == current_user_id))
            .filter(cls.deleted_at.is_(None))
            .all()
        )

        friendship_map = {}
        for friendship in friendships:
            other_id = friendship.user_b_id if friendship.user_a_id == current_user_id else friendship.user_a_id
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
    def add_friendship(user_id: int, other_id: int):
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
            Friend.query
            .filter(Friend.user_a_id == user_id, Friend.user_b_id == other_id)
            .filter(Friend.deleted_at.is_(None))
            .first()
        )

        if existing:
            return existing  # friendship already exists

        # Add friendship
        friendship = Friend(user_a_id=user_id, user_b_id=other_id)
        db.session.add(friendship)
        db.session.commit()

        from zeeguu.core import events
        events.friendship_changed.send(None, user_id=user_id, db_session=db.session)
        events.friendship_changed.send(None, user_id=other_id, db_session=db.session)
        db.session.commit()

        return friendship

    @staticmethod
    def count_active_friends(user_id: int) -> int:
        """Return the current number of friends for a user."""
        return (
                db.session.query(func.count(Friend.id))
                .filter(
                    ((Friend.user_a_id == user_id) | (Friend.user_b_id == user_id)),
                    Friend.deleted_at.is_(None),
                )
                .scalar()
                or 0
        )

    @staticmethod
    def _get_friendship_or_friend_request(friendship, friend_request):
        if friendship:
            return {
                "friend_streak": friendship.current_friend_streak,
                "friend_streak_last_updated": (
                    friendship.friend_streak_last_updated.isoformat()
                    if friendship.friend_streak_last_updated
                    else None
                ),
                "is_accepted": True,
                "created_at": friendship.created_at.isoformat() if friendship.created_at else None,
            }
        elif friend_request:
            return {
                "sender_username": friend_request.sender.username,
                "receiver_username": friend_request.receiver.username,
                "friend_streak": 0,
                "friend_streak_last_updated": None,
                "is_accepted": False,
                "created_at": (
                    friend_request.created_at.isoformat()
                    if friend_request.created_at
                    else None
                ),
            }

