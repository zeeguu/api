import json

import flask
from zeeguu.api.endpoints.feature_toggles import features_for_user
import zeeguu.core
from zeeguu.core.model import User

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api
from ...core.model import UserPreference


@api.route("/learned_language", methods=["GET"])
@cross_domain
@requires_session
def learned_language():
    """
    Each endpoint is defined by a function definition
    of the same form as this one.

    The important information for understanding the
    endpoint is in the annotations before the function
    and in the comment immediately after the function
    name.

    Two types of annotations are important:

     @endpoints.route gives you the endpoint name together
        with the expectd HTTP method
        it is normally appended to the API_URL (https://www.zeeguu.unibe.ch/)

     @with_session means that you must submit a session
        argument together wit your API request
        e.g. API_URL/learned_language?session=123141516
    """
    user = User.find_by_id(flask.g.user_id)
    return user.learned_language.code


@api.route("/learned_language/<language_code>", methods=["POST"])
@cross_domain
@requires_session
def learned_language_set(language_code):
    """
    Set the learned language
    :param language_code: one of the ISO language codes
    :return: "OK" for success
    """
    user = User.find_by_id(flask.g.user_id)
    user.set_learned_language(language_code, session=zeeguu.core.model.db.session)
    zeeguu.core.model.db.session.commit()
    return "OK"


@api.route("/native_language", methods=["GET"])
@cross_domain
@requires_session
def native_language():
    user = User.find_by_id(flask.g.user_id)
    return user.native_language.code


@api.route("/native_language/<language_code>", methods=["POST"])
@cross_domain
@requires_session
def native_language_set(language_code):
    """
    :param language_code:
    :return: OK for success
    """
    user = User.find_by_id(flask.g.user_id)
    user.set_native_language(language_code)
    zeeguu.core.model.db.session.commit()
    return "OK"


@api.route("/learned_and_native_language", methods=["GET"])
@cross_domain
@requires_session
def learned_and_native_language():
    """
    Get both the native and the learned language
    for the user in session
    :return:
    """
    user = User.find_by_id(flask.g.user_id)
    res = dict(native=user.native_language_id, learned=user.learned_language_id)
    return json_result(res)


@api.route("/get_user_details", methods=("GET",))
@cross_domain
@requires_session
def get_user_details():
    """
    after the login, this information might be useful to be displayed
    by an app
    :param lang_code:
    :return:
    """
    user = User.find_by_id(flask.g.user_id)
    details_dict = user.details_as_dictionary()
    details_dict["features"] = features_for_user(user)

    return json_result(details_dict)


@api.route("/user_settings", methods=["POST"])
@cross_domain
@requires_session
def user_settings():
    """
    set the native language of the user in session
    :return: OK for success
    """

    data = flask.request.form
    user = User.find_by_id(flask.g.user_id)

    submitted_name = data.get("name", None)
    if submitted_name:
        user.name = submitted_name

    submitted_native_language_code = data.get("native_language_code", None)
    if not submitted_native_language_code:
        submitted_native_language_code = data.get("native_language", None)

    if submitted_native_language_code:
        user.set_native_language(submitted_native_language_code)

    # deprecating the larned_language_code
    # TR: Do we still need this?
    submitted_learned_language_code = data.get("learned_language_code", None)
    if not submitted_learned_language_code:
        submitted_learned_language_code = data.get("learned_language", None)

    cefr_level = data.get("cefr_level", None)
    if cefr_level is None:
        return "ERROR"

    if submitted_learned_language_code:
        user.set_learned_language(
            submitted_learned_language_code, cefr_level, zeeguu.core.model.db.session
        )

    submitted_email = data.get("email", None)
    if submitted_email:
        user.email = submitted_email

    zeeguu.core.model.db.session.add(user)
    zeeguu.core.model.db.session.commit()
    return "OK"


@api.route("/send_feedback", methods=["POST"])
@cross_domain
@requires_session
def send_feedback():

    message = flask.request.form.get("message", "")
    context = flask.request.form.get("context", "")
    print(message)
    print(context)
    from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

    user = User.find_by_id(flask.g.user_id)
    ZeeguuMailer.send_feedback("Feedback", context, message, user)
    return "OK"
