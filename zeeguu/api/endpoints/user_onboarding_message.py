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
    user = User.find_by_id(flask.g.user_id)
    onboarding_message_id = flask.request.args.get("onboarding_message_id", None)

    if not onboarding_message_id:
        return json_result({"error": "onboarding_message_id required"}, status=400)

    return json_result(
        {
            "shown": UserOnboardingMessage.has_message_shown_time(
                user.id, int(onboarding_message_id)
            )
        }
    )


@api.route("/get_onboarding_message_for_user", methods=["POST"])
@cross_domain
@requires_session
def get_onboarding_message_for_user():
    """
    Records that an onboarding message was shown to the user.
    Frontend calls this when the message appears on screen.
    Uses the find_or_create pattern: row was pre-created for user,
    now just mark when it was shown.
    """
    user = User.find_by_id(flask.g.user_id)
    data = flask.request.form
    onboarding_message_id = data.get("onboarding_message_id", None)
    
    if not onboarding_message_id:
        return json_result({"error": "onboarding_message_id required"}, status=400)
    
    user_onboarding_message = UserOnboardingMessage.find_or_create_for_user_and_message(
        db_session, user.id, int(onboarding_message_id)
    )
    UserOnboardingMessage.set_message_shown_time(user_onboarding_message.id, db_session)
    db_session.commit()
    
    onboarding_data = {
        "user_onboarding_message_id": user_onboarding_message.id,
        "onboarding_message_id": int(onboarding_message_id)
    }
    
    return json_result(onboarding_data)


@api.route("/set_onboarding_message_click_time", methods=["POST"])
@cross_domain
@requires_session
def set_onboarding_message_click_time():
    data = flask.request.form
    # user = User.find_by_id(flask.g.user_id)
    user_onboarding_message_id = data.get("user_onboarding_message_id", None)
    UserOnboardingMessage.update_user_onboarding_message_time(user_onboarding_message_id, db_session)
    db_session.commit()

    return "OK"