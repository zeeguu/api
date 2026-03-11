from sqlalchemy import Column, Integer, DateTime, ForeignKey, func, or_
from sqlalchemy.orm import relationship
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
    
    
    def update_friend_streak(self):
        """
        Update friend_streak if both users practiced today or on consecutive days.
        Requires UserLanguage.last_practiced for both users.
        """
        from zeeguu.core.model.user_language import UserLanguage
        user_lang = UserLanguage.query.filter(UserLanguage.user_id == self.user_id).first()
        friend_lang = UserLanguage.query.filter(UserLanguage.user_id == self.friend_id).first()
        if not user_lang or not friend_lang:
            self.friend_streak = 0
            if db.session:
                db.session.add(self)
                db.session.commit()
            return
        
        user_date = user_lang.last_practiced.date() if user_lang.last_practiced else None
        friend_date = friend_lang.last_practiced.date() if friend_lang.last_practiced else None
        today = datetime.now().date()
        # Both practiced today
        if user_date == today and friend_date == today:
            # Check if yesterday was also a streak day
            yesterday = today - timedelta(days=1)
            if user_date == yesterday and friend_date == yesterday:
                self.friend_streak = (self.friend_streak or 0) + 1
            else:
                self.friend_streak = 1
        else:
            self.friend_streak = 1
        if db.session:
            db.session.add(self)
            db.session.commit()

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

            results.append({
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                },
                "friendship": {
                    "id": friendship.id if friendship else None,
                    "created_at": friendship.created_at.isoformat() if friendship and friendship.created_at else None,
                } if friendship else None,
                "friend_request": {
                    "id": friend_request.id if friend_request else None,
                    "sender_id": friend_request.sender_id if friend_request else None,
                    "receiver_id": friend_request.receiver_id if friend_request else None,
                    "status": friend_request.status if friend_request else None,
                    "created_at": friend_request.created_at.isoformat() if friend_request and friend_request.created_at else None,
                } if friend_request else None
            })
        return results


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