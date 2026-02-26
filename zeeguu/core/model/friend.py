from sqlalchemy import Column, Integer, DateTime, Enum, ForeignKey, func, or_
from sqlalchemy.orm import relationship
from zeeguu.core.model.db import db
from zeeguu.core.model.user import User  # assuming you have a User model


class Friend(db.Model):
	__tablename__ = "friends"
	__table_args__ = {"mysql_collate": "utf8_bin"}

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
	friend_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
	created_at = Column(DateTime, default=func.now())

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