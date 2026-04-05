import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import User
from zeeguu.core.model import UserLanguage
from zeeguu.core.model.friend import Friend
from zeeguu.core.model.friend_request import FriendRequest
from zeeguu.core.model.user_avatar import UserAvatar
from zeeguu.logging import log
from . import api


# ---------------------------------------------------------------------------
@api.route("/get_friends", methods=["GET"])
@api.route("/get_friends/<username>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_friends(username: str = None):
    """
    Get all friends for the current user, or for a friend by user_id.
    """
    requester_id = flask.g.user_id
    if username is not None:
        used_user = User.find_by_username(username)
        if used_user is None:
            return []
        used_user_id = used_user.id
        if requester_id != used_user_id and not Friend.are_friends(requester_id, used_user_id):
            return make_error(403, "You can only view friends for yourself or your friends.")
    else:
        used_user_id = requester_id

    friend_details = Friend.get_friends_with_details(used_user_id)
    result = [
        _serialize_user_with_friendship_details(friend_detail)
        for friend_detail in friend_details
    ]
    log(f"get_friends: requester_id={requester_id} requested friends for user_id={used_user_id}; count={len(result)}")
    return json_result(result)


# ---------------------------------------------------------------------------
@api.route("/get_number_of_received_friend_requests", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_number_of_received_friend_requests():
    """
    Get the number of friend requests received by a user.
    """
    return json_result(FriendRequest.get_number_of_received_friend_requests_for_user(flask.g.user_id))

# ---------------------------------------------------------------------------
@api.route("/get_received_friend_requests", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_received_friend_requests():
    """
    Get all friend requests received by a user.
    """
    friend_requests = FriendRequest.get_received_friend_requests_for_user(flask.g.user_id)
    result = []
    for req in friend_requests:
        serialized_req = _serialize_friend_request(req[0])
        serialized_req["sender"]["avatar"] = _serialize_user_avatar(req[1])
        result.append(serialized_req)
    return json_result(result)


# ---------------------------------------------------------------------------
@api.route("/get_sent_friend_requests", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_sent_friend_requests():
    """
    Get all friend requests sent by a user.
    """
    friend_requests = FriendRequest.get_sent_friend_requests_for_user(flask.g.user_id)
    result = [_serialize_friend_request(req) for req in friend_requests]
    return json_result(result)


# ---------------------------------------------------------------------------
@api.route("/send_friend_request", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def send_friend_request():
    """
    Send a friend request from sender (currently logged-in user) to receiver
    """
    try:
        sender_id = flask.g.user_id
        receiver_id = get_receiver_from_request(sender_id)
        friend_request = FriendRequest.send_friend_request(sender_id, receiver_id)
        response = _serialize_friend_request(friend_request)
        return json_result(response)
    except ValueError as e:
        log(f"send_friend_request: error sending friend request from user_id={sender_id} to user_id={receiver_id} - {str(e)}")
        return make_error(400, str(e))
    except NoResultFound:
        log(f"send_friend_request: user not found for user_id={receiver_id}")
        return make_error(404, "User not found")


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
    receiver_username = request.json.get("receiver_username")
    receiver = User.find_by_username(receiver_username)
    if receiver is None:
        raise json_result({"success": False})
    receiver_id = receiver.id

    is_deleted = FriendRequest.delete_friend_request(sender_id, receiver_id)
    return json_result({"success": is_deleted})


# ---------------------------------------------------------------------------
@api.route("/accept_friend_request", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def accept_friend_request():
    """
    Accept a friend request between sender and receiver, and create a friendship
    """
    try:
        receiver_id = flask.g.user_id
        sender_id = get_sender_from_request(receiver_id)
    except ValueError as e:
        log(f"accept_friend_request: invalid request from user_id={sender_id} to user_id={receiver_id} - {str(e)}")
        return make_error(400, str(e))

    friendship = FriendRequest.accept_friend_request(sender_id, receiver_id)
    if friendship is None:
        log(f"accept_friend_request: no friend request found from user_id={sender_id} to user_id={receiver_id}")
        return make_error(404, "No friend request found to accept")

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
    try:
        receiver_id = flask.g.user_id
        sender_id = get_sender_from_request(receiver_id)
    except ValueError as e:
        log(f"send_friend_request: invalid request from user_id={sender_id} to user_id={receiver_id} - {str(e)}")
        return make_error(400, str(e))

    is_rejected = FriendRequest.reject_friend_request(sender_id, receiver_id)
    return json_result({"success": is_rejected})


# ---------------------------------------------------------------------------
@api.route("/unfriend", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def unfriend():
    """
    Unfriend two users by deleting the Friend row (friendship record) in the database.
    """
    try:
        sender_id = flask.g.user_id
        receiver_id = get_receiver_from_request(sender_id)
    except ValueError as e:
        log(f"send_friend_request: invalid request from user_id={sender_id} to user_id={receiver_id} - {str(e)}")
        return make_error(400, str(e))

    is_removed = Friend.remove_friendship(sender_id, receiver_id)
    log(f"unfriend: user_id={sender_id} unfriended user_id={receiver_id} - success={is_removed}")
    return json_result({"success": is_removed})


# ---------------------------------------------------------------------------
# Search and discover friends endpoints below
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
@api.route("/search_users", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def search_by_search_term():
    """
    Search for users matching the search term.
    """
    search_term = flask.request.args.get("query")
    if not search_term or search_term.strip() == "":
        return json_result([])

    search_term = search_term.strip()
    user_details = Friend.search_users(flask.g.user_id, search_term)
    result = [
        _serialize_user_with_friendship_details(user_detail)
        for user_detail in user_details
    ]

    log(f"search_users: user_id={flask.g.user_id} searched for search_term='{search_term}' and found {len(result)} results")
    return json_result(result)


# ---------------------------------------------------------------------------
# Helper functions below
# ---------------------------------------------------------------------------

def _serialize_user_with_friendship_details(user_data):
    result = _serialize_user(user_data.get("user"))
    result["friendship"] = _serialize_friendship(user_data.get("friendship"))
    result["friend_request"] = _serialize_friend_request(user_data.get("friend_request"))
    result["avatar"] = _serialize_user_avatar(user_data.get("user_avatar"))
    result["languages"] = _serialize_user_languages(user_data.get("user_languages"))
    return result


def _serialize_user(user: User):
    return {
        "name": user.name,
        "username": user.username,
    }


def _serialize_friendship(friendship: Friend, status: str = "accepted"):
    if friendship is None:
        return None

    return {
        "sender_username": friendship.user.username,
        "receiver_username": friendship.friend.username,
        "created_at": friendship.created_at,
        "friend_request_status": status,
        "friend_streak": friendship.friend_streak,
        "friend_streak_last_updated": friendship.friend_streak_last_updated.isoformat() if friendship.friend_streak_last_updated else None,
    }


def _serialize_user_avatar(user_avatar: UserAvatar):
    if user_avatar is None:
        return None

    return {
        "image_name": user_avatar.image_name,
        "character_color": user_avatar.character_color,
        "background_color": user_avatar.background_color,
    }


def _serialize_user_languages(user_languages: list[UserLanguage]):
    if not user_languages:
        return None

    user_languages.sort(key=lambda ul: ul.max_streak, reverse=True)
    return [{
        "code": user_language.language.code,
        "language": user_language.language.name,
        "daily_streak": user_language.daily_streak,
        "max_streak": user_language.max_streak,
    } for user_language in user_languages]


def _serialize_friend_request(friend_request: FriendRequest):
    """
    Serialize a FriendRequest object into JSON-friendly dict.

    Args:
        friend_request (FriendRequest): The friend request object

    Returns:
        dict: JSON-serializable dictionary
    """
    if not friend_request:
        return None

    return {
        "sender": {
            "name": friend_request.sender.name,
            "username": friend_request.sender.username,
        },
        "receiver": {
            "name": friend_request.receiver.name,
            "username": friend_request.receiver.username,
        },
        "friend_request_status": friend_request.status,
        "created_at": friend_request.created_at.isoformat() if friend_request.created_at else None,
        "responded_at": friend_request.responded_at.isoformat() if friend_request.responded_at else None,
    }


def get_sender_from_request(receiver_id:int, sender_field="sender_username"):
    """
    Extract sender_id from request.json and current session.
    Returns: validated sender_id
    Raises ValueError with message if validation fails.
    """
    sender_username = request.json.get(sender_field)
    if sender_username is None:
        raise ValueError("Missing sender username")
    sender = User.find_by_username(sender_username)
    if sender is None:
        raise ValueError("Sender user not found")
    sender_id = sender.id

    status_code, error_message = _validate_friend_request_participants(sender_id, receiver_id)
    if status_code >= 400:
        raise ValueError(error_message)

    return sender_id

def get_receiver_from_request(sender_id:int, receiver_field="receiver_username"):
    """
    Extract receiver_id from request.json and current session.
    Returns: validated receiver_id
    Raises ValueError with message if validation fails.
    """
    receiver_username = request.json.get(receiver_field)
    if receiver_username is None:
        raise ValueError("Missing receiver username")
    receiver = User.find_by_username(receiver_username)
    if receiver is None:
        raise ValueError("Receiver user not found")
    receiver_id = receiver.id

    status_code, error_message = _validate_friend_request_participants(sender_id, receiver_id)
    if status_code >= 400:
        raise ValueError(error_message)

    return receiver_id


def _validate_friend_request_participants(sender_id: int, receiver_id: int) -> tuple[int, str]:
    """
    :param sender_id: the user_id of the sender of the friend request
    :param receiver_id: the user_id of the receiver of the friend request
    Validate the friend request data, return (status_code, error_message)

    :return: (status_code, error_message)
    """
    if sender_id is None or receiver_id is None:
        return 422, "invalid data sender or/and receiver"

    if sender_id == receiver_id:
        return 422, "cannot send friend request to yourself"

    return 200, "ok"
