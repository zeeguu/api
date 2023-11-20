import json

import flask
from zeeguu.api.endpoints.feature_toggles import features_for_user
import zeeguu.core

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, with_session
from . import api
from ...core.model import UserPreference


@api.route("/learned_language", methods=["GET"])
@cross_domain
@with_session
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

    return flask.g.user.learned_language.code


@api.route("/learned_language/<language_code>", methods=["POST"])
@cross_domain
@with_session
def learned_language_set(language_code):
    """
    Set the learned language
    :param language_code: one of the ISO language codes
    :return: "OK" for success
    """
    flask.g.user.set_learned_language(
        language_code, session=zeeguu.core.model.db.session
    )
    zeeguu.core.model.db.session.commit()
    return "OK"


@api.route("/native_language", methods=["GET"])
@cross_domain
@with_session
def native_language():
    return flask.g.user.native_language.code


@api.route("/native_language/<language_code>", methods=["POST"])
@cross_domain
@with_session
def native_language_set(language_code):
    """
    :param language_code:
    :return: OK for success
    """
    flask.g.user.set_native_language(language_code)
    zeeguu.core.model.db.session.commit()
    return "OK"


@api.route("/learned_and_native_language", methods=["GET"])
@cross_domain
@with_session
def learned_and_native_language():
    """
    Get both the native and the learned language
    for the user in session
    :return:
    """
    u = flask.g.user
    res = dict(native=u.native_language_id, learned=u.learned_language_id)
    return json_result(res)


@api.route("/get_user_details", methods=("GET",))
@cross_domain
@with_session
def get_user_details():
    """
    after the login, this information might be useful to be displayed
    by an app
    :param lang_code:
    :return:
    """
    details_dict = flask.g.user.details_as_dictionary()
    details_dict["features"] = features_for_user(flask.g.user)

    return json_result(details_dict)


@api.route("/user_settings", methods=["POST"])
@cross_domain
@with_session
def user_settings():
    """
    set the native language of the user in session
    :param language_code:
    :return: OK for success
    """

    data = flask.request.form
    print(flask.request)

    submitted_name = data.get("name", None)
    if submitted_name:
        flask.g.user.name = submitted_name

    submitted_native_language_code = data.get("native_language_code", None)
    if not submitted_native_language_code:
        submitted_native_language_code = data.get("native_language", None)

    if submitted_native_language_code:
        flask.g.user.set_native_language(submitted_native_language_code)

    # deprecating the larned_language_code
    submitted_learned_language_code = data.get("learned_language_code", None)
    if not submitted_learned_language_code:
        submitted_learned_language_code = data.get("learned_language", None)

    if submitted_learned_language_code:
        flask.g.user.set_learned_language(
            submitted_learned_language_code, zeeguu.core.model.db.session
        )

    language_level = data.get("language_level_data", None)
    if language_level:
        submitted_learned_language_data = json.loads(language_level)
        for language_level in submitted_learned_language_data:
            flask.g.user.set_learned_language_level(
                language_level[0], language_level[1], zeeguu.core.model.db.session
            )

    submitted_email = data.get("email", None)
    if submitted_email:
        flask.g.user.email = submitted_email

    zeeguu.core.model.db.session.add(flask.g.user)
    zeeguu.core.model.db.session.commit()
    return "OK"


@api.route("/send_feedback", methods=["POST"])
@cross_domain
@with_session
def send_feedback():

    message = flask.request.form.get("message", "")
    context = flask.request.form.get("context", "")
    print(message)
    print(context)
    from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

    ZeeguuMailer.send_feedback("Feedback", context, message, flask.g.user)
    return "OK"
