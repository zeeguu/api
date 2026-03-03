import flask
from flask import request
from zeeguu.core.model import User
from zeeguu.core.model.friend import Friend
from zeeguu.core.model.friend_request import FriendRequest
from zeeguu.api.utils.json_result import json_result
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api

# import re
# from langdetect import detect
# import json
# from zeeguu.logging import log

# ---------------------------------------------------------------------------
@api.route("/get_friends", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_friends():
   """
   Get all friends of current user with flask.g.user_id
   """
   friends = Friend.get_friends(flask.g.user_id)
   return json_result(_seralize_users(friends))


# ---------------------------------------------------------------------------
@api.route("/get_friend_requests", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_friend_requests():
   """
   Get all friend requests of a user
   """

   friendRequest = FriendRequest.get_friend_requests_for_user(flask.g.user_id)
   result = [_serialize_friend_request(req) for req in friendRequest]
   return json_result(result)

@api.route("/get_pending_friend_requests", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_pending_friend_requests():
   """
   Get all pending friend requests of a user
   """

   friendRequest = FriendRequest.get_pending_friend_requests_for_user(flask.g.user_id)
   result = [_serialize_friend_request(req) for req in friendRequest]
   return json_result(result)


# ---------------------------------------------------------------------------
@api.route("/send_friend_request", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def send_friend_request():
   """
   Send a friend request from sender (current user with flask.g.user_id) to receiver
   """
   sender_id = flask.g.user_id
   receiver_id = request.json.get("receiver_id")

   status_code, error_message = _is_friend_request_valid(sender_id, receiver_id)
   if status_code >= 400:
      flask.abort(status_code, error_message)

   try: 
      friend_request = FriendRequest.send_friend_request(sender_id, receiver_id)
      response = _serialize_friend_request(friend_request)
      return json_result(response)
   except ValueError as e:
      return flask.abort(400, str(e))
   except NoResultFound:
      return flask.abort(404, "User not found")


# ---------------------------------------------------------------------------
@api.route("/delete_friend_request", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def delete_friend_request():
   """
   Delete a friend request between sender and receiver
   """
   sender_id = flask.g.user_id
   receiver_id = request.json.get("receiver_id")
   
   status_code, error = _is_friend_request_valid(sender_id, receiver_id)
   if status_code >= 400:
      return flask.abort(status_code, error)
   
   is_deleted = FriendRequest.delete_friend_request(sender_id, receiver_id)
   return json_result(str(is_deleted))

# ---------------------------------------------------------------------------
@api.route("/accept_friend_request", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def accept_friend_request():
   """
   Accept a friend request between sender and receiver, and create a friendship
   """
   # current user is the receiver of the friend request
   receiver_id = flask.g.user_id 
   sender_id = request.json.get("sender_id")
   print(f"sender_id: {sender_id}")
   status_code, error = _is_friend_request_valid(sender_id, receiver_id)
   if status_code >= 400:
      return flask.abort(status_code, error)
   
   friendship = FriendRequest.accept_friend_request(sender_id, receiver_id)
   if friendship is None:
      return flask.abort(404, "No friend request found to accept")
   
   response = _serialize_friendship(friendship)
   return json_result(response)

# ---------------------------------------------------------------------------
@api.route("/reject_friend_request", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def reject_friend_request():
   """
   Reject a friend request between sender and receiver, and delete the friend request record in the database
   """
   # current user is the receiver of the friend request
   receiver_id = flask.g.user_id 
   sender_id = request.json.get("sender_id")
   status_code, error_message = _is_friend_request_valid(sender_id, receiver_id)
   
   if status_code >= 400:
      return flask.abort(status_code, error_message)
   
   is_rejected = FriendRequest.reject_friend_request(sender_id, receiver_id)
   return json_result(is_rejected)

# ---------------------------------------------------------------------------
@api.route("/unfriend", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def unfriend():
   """
   unfriend a friendship between user1 and user2, and delete the friends row (friendship record) in the database
   """
   sender_id = flask.g.user_id 
   receiver_id = request.json.get("receiver_id")
   
   status_code, error_message = _is_friend_request_valid(sender_id, receiver_id)
   if status_code >= 400:
      return flask.abort(status_code, error_message)
   
   is_removed = Friend.remove_friendship(sender_id, receiver_id)
   return json_result(str(is_removed))


# ---------------------------------------------------------------------------
# Search and discover friends endpoints below
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
@api.route("/discover_friends/<username>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def discover_by_username(username):
   """
   Search for new friends with <username> of a user by user_id
   """
   user_id = flask.g.user_id
   new_friends = Friend.search_for_new_friends(user_id, username)
   return json_result(_seralize_users(new_friends))

# ---------------------------------------------------------------------------
@api.route("/search_users/<username>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def search_by_username(username):
  return flask.abort(501, "Not implemented yet")

# ---------------------------------------------------------------------------
@api.route("/search_friends/<username>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def search_friends(username):
   """
   Search among friends with <username> for current user with flask.g.user_id
   """
   return flask.abort(501, "Not implemented yet")

# ---------------------------
# Helper functions below
# ---------------------------

# def _serialize_friend_request(friend_request: FriendRequest):
#    result = {
#       "id": friend_request.id,
#       "sender_id": friend_request.sender_id,
#       "receiver_id": friend_request.receiver_id,
#       "created_at": friend_request.created_at,
#       "reponded_at": friend_request.responded_at,
#       "status": friend_request.status,
#    }
#    return result


def _serialize_friend_request(fr: FriendRequest):
    """
    Serialize a FriendRequest object into JSON-friendly dict.

    Args:
        fr (FriendRequest): The friend request object
        current_user_id (int): Optional, to simplify sender/receiver info

    Returns:
        dict: JSON-serializable dictionary
    """
    return {
        "id": fr.id,
        "sender": {
            "id": fr.sender.id, # This is the user_id is that nesessary?
            "name": fr.sender.name, # This will be updated to username
            "username": fr.sender.username, # This will be updated to username
            "email": fr.sender.email, # Is this relevant?
        },
        "receiver": {
            "id": fr.receiver.id, # This is the user_id is that nesessary?
            "name": fr.receiver.name, # This will be updated to username
            "username": fr.receiver.username, # This will be updated to username
            "email": fr.receiver.email, # Is this relevant?
        },
        "status": fr.status,
        "created_at": fr.created_at.isoformat() if fr.created_at else None,
        "responded_at": fr.responded_at.isoformat() if fr.responded_at else None,
    }

def _serialize_friendship(friendship: Friend, status: str = "accepted"):
   result = {
      "id": friendship.id,
      "sender_id": friendship.user_id,
      "receiver_id": friendship.friend_id,
      "created_at": friendship.created_at,
      "status": status,
   }
   return json_result(result)

def _serialize_user(user: User):
   return {
      "id": user.id,
      "name": user.name,
      "username": user.username,
      "email": user.email,
   }

def _seralize_users(users: list[User]):
   return [_serialize_user(user) for user in users]


def _is_friend_request_valid(sender_id, receiver_id)-> tuple[int, str]:
   """
   :param sender_id: the user_id of the sender of the friend request
   :param receiver_id: the user_id of the receiver of the friend request
   Validate the friend request data, return (status_code, error_message)

   :return: (status_code, error_message)
   """
   if sender_id is None or receiver_id is None:
      return 422, "invalid data sender_id or/and receiver_id"
   
   if sender_id == receiver_id:
      return 422, "cannot send friend request to yourself"

   return 200, "ok"