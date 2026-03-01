import flask
from flask import request
from zeeguu.core.model import Article, Language, User, Topic, UserArticle, UserArticleBrokenReport
from zeeguu.core.model.friend import Friend
from zeeguu.core.model.friend_request import FriendRequest
from zeeguu.core.model.article_topic_user_feedback import ArticleTopicUserFeedback
from zeeguu.api.utils.json_result import json_result
from zeeguu.core.model.personal_copy import PersonalCopy
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api, db_session
from zeeguu.core.model.article import HTML_TAG_CLEANR

# import re
# from langdetect import detect
# import json
# from zeeguu.logging import log



# ---------------------------------------------------------------------------
@api.route("/get_friends/<user_id>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
# @requires_session
def get_friends(user_id):
   """
   Get all friends of a user
   """
   friends = Friend.get_friends(user_id)
   for friend in friends:
      print(friend.email)
   return "ok"
   


# ---------------------------------------------------------------------------
@api.route("/get_friend_requests/<user_id>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
# @requires_session
def get_friend_requests(user_id):
   friendRequest : list[FriendRequest] = FriendRequest.get_friend_requests_for_user(user_id)
      
   return [_serialize_friend_request(req) for req in friendRequest]

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
            "email": fr.sender.email, # Is this relevant?
        },
        "status": fr.status,
        "created_at": fr.created_at.isoformat() if fr.created_at else None,
        "responded_at": fr.responded_at.isoformat() if fr.responded_at else None,
    }

# ---------------------------------------------------------------------------
@api.route("/send_friend_request", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
# @requires_session
def send_friend_request():
   sender_id = request.form.get("sender_id", type=int)
   receiver_id = request.form.get("receiver_id", type=int)

   if sender_id is None or receiver_id is None:
      return "error" 
   
   if sender_id == receiver_id:
      return "error" # TODO: Handle error 

   friend_request = FriendRequest.send_friend_request(sender_id, receiver_id)
   return _seralize_friend_request(friend_request)

def _seralize_friend_request(friend_request: FriendRequest):
   return {
      "id": friend_request.id,
      "sender_id": friend_request.sender_id,
      "receiver_id": friend_request.receiver_id,
      "created_at": friend_request.created_at,
      "reponded_at": friend_request.responded_at,
      "status": friend_request.status,
   }

def _seralize_friendship(friendship: Friend, status: str = "accepted"):
   return {
      "id": friendship.id,
      "sender_id": friendship.user_id,
      "receiver_id": friendship.friend_id,
      "created_at": friendship.created_at,
      "status": status,
   }

def _is_friend_request_valid(sender_id, receiver_id)-> tuple[bool, str]:
   if sender_id is None or receiver_id is None:
      return False, "invalid data sender_id or/and receiver_id"
   
   if sender_id == receiver_id:
      return False, "cannot send friend request to yourself"

   return True, "ok"

@api.route("/delete_friend_request", methods=["POST"])
@cross_domain
def delete_friend_reuest():
   sender_id = request.form.get("sender_id", type=int)
   receiver_id = request.form.get("receiver_id", type=int)
   
   is_valid, error = _is_friend_request_valid(sender_id, receiver_id)
   if not is_valid:
      return error
   
   is_deleted = FriendRequest.delete_friend_request(sender_id, receiver_id)
   return str(is_deleted)



@api.route("/accept_friend_request", methods=["POST"])
@cross_domain
def accept_friend_request():
   sender_id = request.form.get("sender_id", type=int)
   receiver_id = request.form.get("receiver_id", type=int)
   is_valid, error = _is_friend_request_valid(sender_id, receiver_id)
   if not is_valid:
      return error
   
   friendship = FriendRequest.accept_friend_request(sender_id, receiver_id)
   if friendship is None:
      return "None"
   return _seralize_friendship(friendship)

@api.route("/reject_friend_request", methods=["POST"])
@cross_domain
def reject_friend_request():
   sender_id = request.form.get("sender_id", type=int)
   receiver_id = request.form.get("receiver_id", type=int)
   is_valid, error = _is_friend_request_valid(sender_id, receiver_id)
   if not is_valid:
      return error
   
   is_rejected = FriendRequest.reject_friend_request(sender_id, receiver_id)

   return str(is_rejected)



@api.route("/unfriend", methods=["POST"])
@cross_domain
def unfriend():
   sender_id = request.form.get("sender_id", type=int)
   receiver_id = request.form.get("receiver_id", type=int)
   is_valid, error = _is_friend_request_valid(sender_id, receiver_id)
   if not is_valid:
      return error
   is_removed = Friend.remove_friendship(sender_id, receiver_id)
   return str(is_removed)


@api.route("/users/search/<username>", methods=["GET"])
@cross_domain
def search_by_username(username):
  pass

@api.route("/users/discover/<user_id>/<username>", methods=["GET"])
@cross_domain
def discover_by_username(user_id, username):
   """
   Search for new friends with <username> of a user by user_id
   """
   user_id = int(user_id)
   if user_id is None:
      return flask.abort(400, "missing user_id")
   
   new_friends = Friend.search_for_new_friends(user_id, username)
   return [_serialize_user(user) for user in new_friends]

def _serialize_user(user: User):
   return {
      "id": user.id,
      "name": user.name,
      "username": user.username,
      "email": user.email,
   }

@api.route("/users/search/<user_id>/friends/<username>", methods=["GET"])
@cross_domain
def search_friends(user_id, username):
   """
   Search for friends with <username> of a user by user_id
   """
   user_id = int(user_id)
   if user_id is None:
      return flask.abort(400, "missing user_id")


