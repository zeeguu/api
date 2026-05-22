import flask

from zeeguu.core.model.user_onboarding_message import UserOnboardingMessage
from zeeguu.core.model.user import User
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api, db_session

@api.route("/get_onboarding_message_status", methods=["GET"])
@cross_domain
@requires_session
def get_onboarding_message_status():
    """
    Checks whether the onboarding message was already shown to the user.
    This endpoint is read-only and returns a boolean only.
    """
    onboarding_message_id = flask.request.args.get("onboarding_message_id", None)

    if not onboarding_message_id:
        return json_result({"error": "onboarding_message_id required"}, status=400)

    try:
        mid = int(onboarding_message_id)
    except ValueError:
        return json_result({"error": "onboarding_message_id must be an integer"}, status=400)

    return json_result({"shown": UserOnboardingMessage.has_message_shown_time(flask.g.user_id, mid)})


@api.route("/mark_onboarding_message_shown", methods=["POST"])  # canonical name
@cross_domain
@requires_session
def mark_onboarding_message_shown():
    """
    Records that an onboarding message was shown to the user.
    Frontend calls this when the message appears on screen.
    Uses lazy creation: if the user/message row does not exist yet,
    it is created now and marked with a shown timestamp.
    """
    data = flask.request.form
    onboarding_message_id = data.get("onboarding_message_id", None)

    if not onboarding_message_id:
        return json_result({"error": "onboarding_message_id required"}, status=400)

    try:
        mid = int(onboarding_message_id)
    except ValueError:
        return json_result({"error": "onboarding_message_id must be an integer"}, status=400)

    user_onboarding_message = UserOnboardingMessage.find_or_create_for_user_and_message(
        db_session, flask.g.user_id, mid
    )
    UserOnboardingMessage.set_message_shown_time(user_onboarding_message.id, db_session)
    db_session.commit()

    onboarding_data = {
        "user_onboarding_message_id": user_onboarding_message.id,
        "onboarding_message_id": int(onboarding_message_id),
    }

    return json_result(onboarding_data)


@api.route("/mark_onboarding_message_dismissed", methods=["POST"])
@cross_domain
@requires_session
def mark_onboarding_message_dismissed():
    data = flask.request.form
    onboarding_message_id = data.get("onboarding_message_id", None)

    if not onboarding_message_id:
        return json_result({"error": "onboarding_message_id required"}, status=400)

    try:
        mid = int(onboarding_message_id)
    except ValueError:
        return json_result({"error": "onboarding_message_id must be an integer"}, status=400)

    user_onboarding_message = UserOnboardingMessage.find_by_user_and_message(flask.g.user_id, mid)

    if not user_onboarding_message:
        return json_result({"error": "not found"}, status=404)

    UserOnboardingMessage.set_message_dismissed_time(user_onboarding_message.id, db_session)
    db_session.commit()

    return "OK"


@api.route("/clear_onboarding_messages", methods=["POST"])
@cross_domain
@requires_session
def clear_onboarding_messages():
    """
    Developer-only helper: removes all onboarding-message history for the
    current user so the dialogues will be shown again from scratch.
    """
    deleted = UserOnboardingMessage.query.filter_by(user_id=flask.g.user_id).delete()
    db_session.commit()
    return json_result({"deleted": deleted})