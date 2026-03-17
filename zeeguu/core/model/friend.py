from sqlalchemy import Column, Integer, DateTime, ForeignKey, func, or_
from sqlalchemy.orm import relationship, object_session
from zeeguu.core.model.db import db
from zeeguu.core.model.user import User  # assuming you have a User model
from datetime import datetime, timedelta

class Friend(db.Model):
    __tablename__ = "friends"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    friend_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    friend_streak = Column(Integer, default=0)  # Tracks streak with this friend
    friend_streak_last_updated = Column(DateTime, nullable=True)
    
    
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

    # Explicit relationships with primaryjoin
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

    @staticmethod
    def get_friends(user_id):
        """Return a list of User objects that are friends with the given user_id."""
        # query where user is either the user_id or the friend_id
        friends = (
            db.session.query(User)
            .join(Friend, or_(Friend.user_id == user_id, Friend.friend_id == user_id))
            .filter(
                    (Friend.user_id == user_id) & (User.id == Friend.friend_id)
                    | (Friend.friend_id == user_id) & (User.id == Friend.user_id)
            )
            .all()
        )
        return friends

    @staticmethod
    def get_friends_with_friendship(user_id: int, exclude_user_id: int = None):
        """Return combined friend user + friendship data for the given user.
        
        exclude_user_id: if provided, that user is omitted from the results.
        """
        friendships : list[Friend] = Friend.query.filter(
            (Friend.user_id == user_id) | (Friend.friend_id == user_id)
        ).all()

        if not friendships:
            return []

        other_user_ids = [
            friendship.friend_id if friendship.user_id == user_id else friendship.user_id
            for friendship in friendships
        ]

        users = User.query.filter(User.id.in_(other_user_ids)).all()
        users_by_id = {user.id: user for user in users}

        result = []
        for friendship in friendships:

            if friendship.user_id == user_id: 
                other_user_id = friendship.friend_id 
            else:
                other_user_id = friendship.user_id

            # Exclude if matches exclude_user_id (usually exclude_user_id is the current user, to avoid returning self as a friend)
            if exclude_user_id is not None and other_user_id == exclude_user_id:
                continue

            friend_user = users_by_id.get(other_user_id)
            if not friend_user:
                continue
            result.append({"user": friend_user, "friendship": friendship})

        return result

    @classmethod
    def are_friends(cls, user1_id: int, user2_id: int) -> bool:
        """Return True if two users are friends (in either direction)."""
        if user1_id is None or user2_id is None:
            return False

        if user1_id == user2_id:
            return True

        friendship = cls.query.filter(
            ((cls.user_id == user1_id) & (cls.friend_id == user2_id)) |
            ((cls.user_id == user2_id) & (cls.friend_id == user1_id))
        ).first()
        return friendship is not None
    
    @classmethod
    def remove_friendship(cls, user1_id: int, user2_id: int)->bool:
        # Look for friendship in either direction
        friendship = cls.query.filter(
            ((cls.user_id == user1_id) & (cls.friend_id == user2_id)) |
            ((cls.user_id == user2_id) & (cls.friend_id == user1_id))
        ).first()

        if friendship:
            db.session.delete(friendship)
            db.session.commit()
            return True
        
        return False
    
    @classmethod
    def find_friend_details(cls, user_id: int, friend_user_id: int):
        """
        Return details_as_dictionary for friend_user_id if user_id and friend_user_id are friends.
        Also includes friends_since and mutual_streak from the friendship record.
        Returns None if not friends or user not found.
        """
        friendship = cls.query.filter(
            ((cls.user_id == user_id) & (cls.friend_id == friend_user_id)) |
            ((cls.user_id == friend_user_id) & (cls.friend_id == user_id))
        ).first()

        from zeeguu.core.model.user import User
        friend = User.find_by_id(friend_user_id)
        details = friend.details_as_dictionary()
        if not friendship: 
            return details  # Not friends, but return basic details without friendship info

        # When there is a friendship, enrich details with friendship info
        details["friends_since"] = friendship.created_at.isoformat() if friendship.created_at else None
        details["mutual_streak"] = friendship.friend_streak or 0
        return details


    @staticmethod
    def search_users(current_user_id: int, term: str, limit: int = 20):
        """
        Search users by username (partial match) or exact email.
        For each user, return:
            - user info
            - friend request status (if any)
            - friendship status (if any)
        """
        from zeeguu.core.model.friend_request import FriendRequest
        
        # Build base query
        filters = []
        if term:
            filters.append(func.lower(User.username).ilike(f"%{term}%")) # ilike for case-insensitive partial match
            filters.append(func.lower(User.email) == term) # exact match for email
            filters.append(func.lower(User.name) == term) # exact match for name
        
        if not filters:
            return []  # nothing to search
        
        query = User.query
        query = query.filter(or_(*filters), User.id != current_user_id).limit(limit)

        results = []
        for user in query.all():
            # Friendship status
            friendship = Friend.query.filter(
                ((Friend.user_id == current_user_id) & (Friend.friend_id == user.id)) |
                ((Friend.user_id == user.id) & (Friend.friend_id == current_user_id))
            ).first()

            # Friend request status
            friend_request = FriendRequest.query.filter(
                ((FriendRequest.sender_id == current_user_id) & (FriendRequest.receiver_id == user.id)) |
                ((FriendRequest.sender_id == user.id) & (FriendRequest.receiver_id == current_user_id))
            ).order_by(FriendRequest.created_at.desc()).first()

            
            friendship_or_friend_request = Friend._get_friendship_or_friendrequest(
                friendship,
                friend_request)
            
            results.append({
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    "friendship": friendship_or_friend_request,
                },
            })
        return results
    @staticmethod
    def _get_friendship_or_friendrequest(friendship, friend_request):
        
        if friendship:
            return {
                "id": friendship.id,
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
                "id": friend_request.id,
                "sender_id": friend_request.sender_id, # TODO: Are these nessesary
                "receiver_id": friend_request.receiver_id, # TODO: are these nesessary
                "friend_streak": 0,
                "friend_streak_last_updated": None,
                "friend_request_status": friend_request.status,
                "created_at": (
                    friend_request.created_at.isoformat()
                    if friend_request.created_at
                    else None
                ),
            }
        
    def add_friendship(user_id: int, friend_id: int):
        """
        Adds a friendship between two users using SQLAlchemy ORM.
        Stores both directions for easy querying.
        """
        # Check if friendship already exists
        existing = Friend.query.filter(
            ((Friend.user_id == user_id) & (Friend.friend_id == friend_id)) |
            ((Friend.user_id == friend_id) & (Friend.friend_id == user_id))
        ).first()

        if existing:
            return existing  # friendship already exists

        # Add friendship
        friendship = Friend(user_id=user_id, friend_id=friend_id)
        db.session.add(friendship)
        db.session.commit()
        db.session.refresh(friendship)
        return friendship