import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.friends.friend_streak import compute_current_streak
from zeeguu.core.model import User
from zeeguu.core.model import UserLanguage
from zeeguu.core.model.db import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.friend_request import FriendRequest
from zeeguu.core.model.friendship import Friendship
from zeeguu.core.model.shared_article import SharedArticle
from zeeguu.core.model.user_avatar import UserAvatar
from zeeguu.logging import log
from . import api


# ---------------------------------------------------------------------------
@api.route("/my_friends", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_my_friends():
    """
        Get all friends for the current user.
    """
    friend_details = Friendship.get_friends_of(flask.g.user_id)
    return json_result([
        _serialize_users_for_get_friends(fd, is_own_friends_list=True)
        for fd in friend_details
    ])

# ---------------------------------------------------------------------------
@api.route("/friends_of/<username>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_friends_of(username):
    """
        Get all friends for the specified user_id.
    """
    target = User.find_by_username(username)
    if target is None:
        return []
    if target.id != flask.g.user_id and not Friendship.are_friends(flask.g.user_id, target.id):
        return make_error(403, "You can only view friends of yourself or your friends.")
    friend_details = Friendship.get_friends_of(target.id)
    return json_result([
        _serialize_users_for_get_friends(fd, is_own_friends_list=False)
        for fd in friend_details
    ])


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
        receiver_id = _get_receiver_from_request(sender_id)
        friend_request = FriendRequest.send_friend_request(sender_id, receiver_id)
        response = _serialize_friend_request(friend_request)
        return json_result(response)
    except ValueError as e:
        log(f"send_friend_request: error - {str(e)}")
        return make_error(400, str(e))
    except NoResultFound:
        log(f"send_friend_request: user not found")
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
        return make_error(404, "User not found")
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
        sender_id = _get_sender_from_request(receiver_id)
    except ValueError as e:
        log(f"accept_friend_request: error - {str(e)}")
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
        sender_id = _get_sender_from_request(receiver_id)
    except ValueError as e:
        log(f"reject_friend_request: error - {str(e)}")
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
    Unfriend two users by deleting the Friendship row (friendship record) in the database.
    """
    try:
        sender_id = flask.g.user_id
        receiver_id = _get_receiver_from_request(sender_id)
    except ValueError as e:
        log(f"unfriend: error - {str(e)}")
        return make_error(400, str(e))

    is_removed = Friendship.remove(sender_id, receiver_id)
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
    users_and_avatars = User.search(flask.g.user_id, search_term)
    friendship_map   = Friendship.get_friendship_map(flask.g.user_id)
    friend_request_map = FriendRequest.get_request_map(flask.g.user_id)
    result = [
        _serialize_users_for_search_users({
            "user": user,
            "user_avatar": avatar,
            "friendship": friendship_map.get(user.id),
            "friend_request": friend_request_map.get(user.id),
        })
        for user, avatar in users_and_avatars
    ]

    log(f"search_users: user_id={flask.g.user_id} searched for search_term='{search_term}' and found {len(result)} results")
    return json_result(result)


# ---------------------------------------------------------------------------
# Helper functions below
# ---------------------------------------------------------------------------
def _serialize_users_for_get_friends(user_data, is_own_friends_list: bool):
    result = _serialize_users_common(user_data, include_friendship_data=is_own_friends_list)
    result["languages"] = _serialize_user_languages(user_data.get("user_languages"), include_streaks=is_own_friends_list)
    return result


def _serialize_users_for_search_users(user_data):
    result = _serialize_users_common(user_data, include_friendship_data=True)
    result["friend_request"] = _serialize_friend_request(user_data.get("friend_request"))
    return result


def _serialize_users_common(user_data, include_friendship_data: bool):
    result = _serialize_user(user_data.get("user"))
    result["avatar"] = _serialize_user_avatar(user_data.get("user_avatar"))
    if include_friendship_data:
        result["friendship"] = _serialize_friendship(user_data.get("friendship"))
    return result


def _serialize_user(user: User):
    return {
        "name": user.name,
        "username": user.username,
    }


def _serialize_friendship(friendship: Friendship):
    if friendship is None:
        return None

    return {
        "created_at": friendship.created_at,
        "friend_streak": compute_current_streak(friendship),
        "friend_streak_last_updated": friendship.friend_streak_last_updated.isoformat() if friendship.friend_streak_last_updated else None
    }


def _serialize_user_avatar(user_avatar: UserAvatar):
    if user_avatar is None:
        return None

    return {
        "image_name": user_avatar.image_name,
        "character_color": user_avatar.character_color,
        "background_color": user_avatar.background_color,
    }


def _serialize_user_languages(user_languages: list[UserLanguage], include_streaks: bool = True):
    if not user_languages:
        return None

    user_languages.sort(key=lambda ul: ul.max_streak, reverse=True)
    result = []
    for user_language in user_languages:
        obj = {
            "code": user_language.language.code,
            "language": user_language.language.name,
        }
        if include_streaks:
            obj["daily_streak"] = user_language.daily_streak
            obj["max_streak"] = user_language.max_streak
        result.append(obj)

    return result


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
        "created_at": friend_request.created_at.isoformat() if friend_request.created_at else None,
    }


def _get_sender_from_request(receiver_id:int, sender_field="sender_username"):
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

def _get_receiver_from_request(sender_id:int, receiver_field="receiver_username"):
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


# ---------------------------------------------------------------------------
@api.route("/share_article_with_friend", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def share_article_with_friend():
    """
    Share an article with an accepted friend.

    Body (JSON): { friend_username, article_id, note? }

    We store the ORIGINAL/parent article id (never the sharer's adapted or
    translated copy) so the recipient's reader adapts it to their own language
    and level on open.
    """
    from_user_id = flask.g.user_id
    friend_username = request.json.get("friend_username")
    article_id = request.json.get("article_id")
    note = request.json.get("note")

    if not friend_username or not article_id:
        return make_error(400, "friend_username and article_id are required")

    friend = User.find_by_username(friend_username)
    if not friend:
        return make_error(404, "user not found")

    to_user_id = friend.id
    if to_user_id == from_user_id:
        return make_error(422, "cannot share with yourself")

    # are_friends returns True for self, so the self-check above must come first.
    if not Friendship.are_friends(from_user_id, to_user_id):
        return make_error(403, "you can only share with your friends")

    article = Article.find_by_id(article_id)
    if not article:
        return make_error(404, "article not found")

    # Everything heavy — resolving the canonical article, generating the
    # recipient's personalized copy, creating the share row, emailing — runs in
    # the background so the sharer's Send returns immediately. The row is created
    # LAST, already carrying the derivative, so a share only ever appears in an
    # inbox once it's ready in the recipient's language (no not-ready window).
    # Trade-off: the client's "Shared with X" is optimistic — the row lands a few
    # seconds later.
    from zeeguu.api.utils.background import run_in_background

    run_in_background(_deliver_share, from_user_id, to_user_id, article_id, note)

    return json_result({"status": "sharing"})


def _deliver_share(from_user_id: int, to_user_id: int, article_id: int, note):
    """Background: resolve the canonical article, generate the recipient's
    personalized copy, create the (complete) share row, and email. Re-queries
    everything by id (own app context / session)."""
    article = Article.find_by_id(article_id)
    recipient = User.find_by_id(to_user_id)
    if not article or not recipient:
        return

    original_id = SharedArticle.resolve_shareable_original_id(db.session, article)

    # Route the share by the recipient's primary language — ALWAYS, even for a
    # plain crawl share that gets no derivative — so it's the "which inbox" key
    # and the per-language inbox surfaces it in the language they actually study.
    delivery_language, level = SharedArticle.compute_delivery_language(recipient)
    delivery_language_id = delivery_language.id if delivery_language is not None else None
    delivery_article_id = (
        _generate_recipient_derivative(article, recipient, delivery_language, level)
        if delivery_language is not None
        else None
    )

    shared = SharedArticle.create(
        db.session, from_user_id, to_user_id, original_id, note,
        delivery_language_id=delivery_language_id,
        delivery_article_id=delivery_article_id,
    )

    try:
        from zeeguu.core.emailer.shared_article import send_shared_article_notification

        send_shared_article_notification(to_user_id, from_user_id, shared.id)
    except Exception as e:
        log(f"share {shared.id}: email notification failed: {e}")


def _generate_recipient_derivative(article, recipient, delivery_language, level):
    """The id of the recipient's personalized derivative, or None.

    Only for upload-based shares (the sharer captured a full body); plain crawl
    shares get None and the recipient opens the canonical article (adapting it
    in the reader). Never raises — a generation failure (LLM/fragment/DB) rolls
    back and degrades to None so the share still lands, routed by its language.
    """
    upload = article.source_upload
    if upload is None:
        return None

    from zeeguu.core.llm_services.simplification_and_classification import (
        create_recipient_derivative,
    )

    try:
        derivative = create_recipient_derivative(
            db.session, upload, delivery_language.code, level
        )
    except Exception as e:
        db.session.rollback()
        log(f"share to user_id={recipient.id}: derivative generation errored "
            f"({e}); recipient will open the canonical article")
        return None

    if derivative is None:
        log(f"share to user_id={recipient.id}: derivative generation failed; "
            f"recipient will open the canonical article")
        return None
    return derivative.id


# ---------------------------------------------------------------------------
@api.route("/articles_shared_with_me", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def articles_shared_with_me():
    """Inbox: non-dismissed articles shared with the current user, newest first."""
    shares = SharedArticle.inbox_for(flask.g.user_id)
    return json_result([s.to_dict() for s in shares])


# ---------------------------------------------------------------------------
@api.route("/mark_shared_article_read", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def mark_shared_article_read():
    """Mark a received share as read. Body (JSON): { shared_article_id }."""
    shared = SharedArticle.find_by_id(request.json.get("shared_article_id"))
    if not shared or shared.to_user_id != flask.g.user_id:
        return make_error(404, "shared article not found")
    shared.mark_read(db.session)
    return json_result("OK")


# ---------------------------------------------------------------------------
@api.route("/dismiss_shared_article", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def dismiss_shared_article():
    """Remove a share from the recipient's inbox. Body (JSON): { shared_article_id }."""
    shared = SharedArticle.find_by_id(request.json.get("shared_article_id"))
    if not shared or shared.to_user_id != flask.g.user_id:
        return make_error(404, "shared article not found")
    shared.dismiss(db.session)
    return json_result("OK")
