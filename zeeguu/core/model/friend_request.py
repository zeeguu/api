from sqlalchemy import Column, Integer, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import relationship
from zeeguu.core.model.db import db
from zeeguu.core.model.user import User  # assuming you have a User model
from zeeguu.core.model.friend import Friend  # assuming you have a User model
from sqlalchemy.exc import NoResultFound

class FriendRequest(db.Model):
   __tablename__ = "friend_requests"
   __table_args__ = {"mysql_collate": "utf8_bin"}

   id = Column(Integer, primary_key=True, autoincrement=True)
   sender_id = Column(Integer, ForeignKey("user.id"), nullable=False)
   receiver_id = Column(Integer, ForeignKey("user.id"), nullable=False)
   status = Column(
      Enum("pending", "accepted", "rejected", name="friend_request_status"),
      default="pending",
   )
   created_at = Column(DateTime, default=func.now())
   responded_at = Column(DateTime, nullable=True)

   # relationships
   # Relationships — explicit foreign_keys and primaryjoin
   sender = relationship(
      User,
      foreign_keys=[sender_id],
      primaryjoin="FriendRequest.sender_id == User.id"
   )
   receiver = relationship(
      User,
      foreign_keys=[receiver_id],
      primaryjoin="FriendRequest.receiver_id == User.id"
   )
   
   def __init__(
         self,
         sender_id,
         receiver_id,
         status="pending"
   ):
      self.sender_id = sender_id
      self.receiver_id = receiver_id
      self.status = status 


   def __repr__(self):
        return "id: "+ str(self.id) + "sender: "+ str(self.sender_id) + "reciever: " + str( self.receiver_id) 

   @classmethod
   def send_friend_request(cls, sender_id: int, receiver_id: int):
    """
    Send a friend request from sender to receiver.

    Args:
        sender_id (int): ID of the user sending the request
        receiver_id (int): ID of the user receiving the request

    Returns:
        FriendRequest: The created friend request object
    """

    # Prevent sending request to self
    if sender_id == receiver_id:
        raise ValueError("Cannot send a friend request to yourself.")

    # Check if users exist
    sender = db.session.query(User).filter_by(id=sender_id).first()
    receiver = db.session.query(User).filter_by(id=receiver_id).first()
    if not sender or not receiver:
        raise ValueError("Sender or receiver does not exist.")

    # Check for existing friend request
    existing_request = db.session.query(cls).filter(
        ((FriendRequest.sender_id == sender_id) & (FriendRequest.receiver_id == receiver_id)) |
        ((FriendRequest.sender_id == receiver_id) & (FriendRequest.receiver_id == sender_id))
    ).first()

    if existing_request:
        raise ValueError("A friend request already exists between these users.")

    # Create new friend request
    new_request = FriendRequest(
        sender_id=sender_id,
        receiver_id=receiver_id,
        status="pending" ## TODO: This should be an enum/constant 
    )

    db.session.add(new_request)
    db.session.commit()
    db.session.refresh(new_request)  # To get the ID and timestamps

    return new_request
   
   @classmethod
   def get_friend_requests_for_user(cls, user_id: int, status: str = "pending"):
         """
         Get friend requests received by a user.

         Args:
            session (Session): SQLAlchemy session
            user_id (int): ID of the user
            status (str): Filter by status ("pending", "accepted", "rejected"). Default: "pending"

         Returns:
            List[FriendRequest]: List of friend request objects
         """
         requests = (
            db.session.query(cls)
            .filter(FriendRequest.receiver_id == user_id)
            .filter(FriendRequest.status == status)
            .order_by(FriendRequest.created_at.desc())
            .all()
         )
         return requests
   @classmethod
   def delete_friend_request(cls, sender_id: int, receiver_id: int)->bool:
        """Delete a friend request between sender and receiver."""
        try:
            fr = db.session.query(cls).filter_by(
                sender_id=sender_id,
                receiver_id=receiver_id,
                status="pending"  # usually only pending requests can be deleted
            ).one()
            db.session.delete(fr)
            db.session.commit()
            return True
        except NoResultFound:
            return False
   
   @classmethod
   def cancel_sent_request(cls, sender_id: int, receiver_id: int)->bool:
      # Look for pending friend request from sender to receiver
      request = cls.query.filter_by(
         sender_id=sender_id,
         receiver_id=receiver_id,
         status="pending"
      ).first()

      if request:
         db.session.delete(request)
         db.session.commit()
         return True
      return False
        
   @classmethod
   def accept_friend_request(cls, sender_id: int, receiver_id: int):
        try:
            # Find the pending request
            fr = db.session.query(cls).filter_by(
                sender_id=sender_id,
                receiver_id=receiver_id,
                status="pending"
            ).one()

            # Update the status
            fr.status = "accepted"
            fr.responded_at = func.now()
            db.session.commit()
            db.session.refresh(fr) # refesh with the new values

            # Optionally create a friendship in your friends table
            Friend.add_friendship(sender_id, receiver_id)
            return fr
        except NoResultFound:
            return None