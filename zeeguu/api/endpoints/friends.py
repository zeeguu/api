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
   
   FriendRequest.send_friend_request()

def delete_friend_reuest():
   pass


def accept_friend_request():
   pass

def search_by_username():
   pass

 
