from datetime import datetime

import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import UserLanguage
from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import User
from zeeguu.core.model.friend import Friend
from zeeguu.core.model.friend_request import FriendRequest
from zeeguu.core.model.user_avatar import UserAvatar
from zeeguu.logging import log, warning
from . import api

LEADERBOARD_METRICS = {
    "exercise_time": Friend.exercise_time_leaderboard,
    "exercises_done": Friend.exercises_done_leaderboard,
    "articles_read": Friend.read_articles_leaderboard,
    "reading_time": Friend.reading_time_leaderboard,
    "listening_time": Friend.listening_time_leaderboard,
}


# ---------------------------------------------------------------------------
@api.route("/get_friends", methods=["GET"])
@api.route("/get_friends/<int:user_id>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_friends(user_id: int = None):
    """
    Get all friends for the current user, or for a friend by user_id.
    """
    requester_id = flask.g.user_id
    used_user_id = user_id if user_id is not None else requester_id

    if used_user_id != requester_id and not Friend.are_friends(requester_id, used_user_id):
        return make_error(403, "You can only view friends for yourself or your friends.")

    friend_details = Friend.get_friends_with_details(used_user_id)
    result = [
        _serialize_user_with_friendship_details(friend_detail)
        for friend_detail in friend_details
    ]
    log(f"get_friends: requester_id={requester_id} requested friends for user_id={used_user_id}; count={len(result)}")
    return json_result(result)


@api.route("/friends_leaderboard", methods=["GET"])
@cross_domain
@requires_session
def friends_leaderboard():
    params, error_response = _parse_leaderboard_query_params()
    if error_response:
        return error_response

    metric = LEADERBOARD_METRICS.get(request.args.get("metric"))

    if not metric:
        return make_error(400, "Invalid leaderboard metric")

    rows = metric(
        flask.g.user_id,
        limit=params["limit"],
        from_date=params["from_date"],
        to_date=params["to_date"],
    )

    result = [
        _serialize_leaderboard_row(row)
        for row in rows
    ]

    return json_result(result)


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
    sender_id = flask.g.user_id
    receiver_id = request.json.get("receiver_id")

    status_code, error_message = _validate_friend_request_participants(sender_id, receiver_id)
    if status_code >= 400:
        log(f"send_friend_request: invalid request from user_id={sender_id} to user_id={receiver_id} - {error_message}")
        return make_error(status_code, error_message)

    try:
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
    receiver_id = request.json.get("receiver_id")

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
    # current user is the receiver of the friend request
    receiver_id = flask.g.user_id
    sender_id = request.json.get("sender_id")

    status_code, error = _validate_friend_request_participants(sender_id, receiver_id)
    if status_code >= 400:
        log(f"accept_friend_request: invalid request from user_id={sender_id} to user_id={receiver_id} - {error}")
        return make_error(status_code, error)

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
    # current user is the receiver of the friend request
    receiver_id = flask.g.user_id
    sender_id = request.json.get("sender_id")

    status_code, error_message = _validate_friend_request_participants(sender_id, receiver_id)

    if status_code >= 400:
        log(f"reject_friend_request: invalid request from user_id={sender_id} to user_id={receiver_id} - {error_message}")
        return make_error(status_code, error_message)

    is_rejected = FriendRequest.reject_friend_request(sender_id, receiver_id)
    return json_result({"success": is_rejected})


# ---------------------------------------------------------------------------
@api.route("/unfriend", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def unfriend():
    """
    Unfriend two users by deleting the Friends row (friendship record) in the database.
    """
    sender_id = flask.g.user_id
    receiver_id = request.json.get("receiver_id")

    status_code, error_message = _validate_friend_request_participants(sender_id, receiver_id)
    if status_code >= 400:
        log(f"unfriend: invalid request from user_id={sender_id} to user_id={receiver_id} - {error_message}")
        return make_error(status_code, error_message)

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
        "id": user.id,
        "name": user.name,
        "username": user.username,
    }


def _serialize_friendship(friendship: Friend, status: str = "accepted"):
    if friendship is None:
        return None

    return {
        "sender_id": friendship.user_id,
        "receiver_id": friendship.friend_id,
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

    return [{
        "language": user_language.language.as_dictionary(),
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
            "id": friend_request.sender.id,  # This is the user_id is that necessary?
            "name": friend_request.sender.name,
            "username": friend_request.sender.username,
        },
        "receiver": {
            "id": friend_request.receiver.id,  # This is the user_id is that necessary?
            "name": friend_request.receiver.name,
            "username": friend_request.receiver.username,
        },
        "friend_request_status": friend_request.status,
        "created_at": friend_request.created_at.isoformat() if friend_request.created_at else None,
        "responded_at": friend_request.responded_at.isoformat() if friend_request.responded_at else None,
    }


def _serialize_leaderboard_row(row):
    user_id = getattr(row, "user_id", None) or row[0]
    name = getattr(row, "name", None) or row[1]
    username = getattr(row, "username", None) or row[2]
    value = getattr(row, "value", None) or row[3]

    return {
        "user": {
            "id": user_id,
            "name": name,
            "username": username,
            "user_avatar": {
                "image_name": getattr(row, "image_name", None),
                "character_color": getattr(row, "character_color", None),
                "background_color": getattr(row, "background_color", None),
            }
        },
        "value": value,
    }


def _validate_friend_request_participants(sender_id, receiver_id) -> tuple[int, str]:
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


def _parse_leaderboard_query_params():
    """
    Parse common leaderboard query params:
        limit: positive integer
        from_date: ISO datetime string (optional)
        to_date: ISO datetime string (optional)
    """
    limit = 20
    limit_arg = request.args.get("limit")
    if limit_arg is not None:
        try:
            limit = int(limit_arg)
        except ValueError:
            return None, make_error(400, "limit must be an integer")

        if limit <= 0:
            return None, make_error(400, "limit must be greater than 0")

    from_date_str = request.args.get("from_date")
    to_date_str = request.args.get("to_date")

    from_date = None
    to_date = None

    if from_date_str:
        from_date, error = _parse_iso_datetime(from_date_str, "from_date")
        if error:
            return None, error

    if to_date_str:
        to_date, error = _parse_iso_datetime(to_date_str, "to_date")
        if error:
            return None, error

    if from_date and to_date and from_date > to_date:
        return None, make_error(400, "from_date must be before or equal to to_date")

    return {
        "limit": limit,
        "from_date": from_date,
        "to_date": to_date,
    }, None


def _parse_iso_datetime(value: str, param_name: str):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        return parsed, None
    except ValueError:
        return None, make_error(400, f"{param_name} must be a valid ISO datetime")
