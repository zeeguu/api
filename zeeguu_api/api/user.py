import flask
import zeeguu

from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session
from . import api


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
    return json_result(flask.g.user.details_as_dictionary())


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

     @api.route gives you the endpoint name together
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
    flask.g.user.set_learned_language(language_code)
    zeeguu.db.session.commit()
    return "OK"


@api.route("/native_language", methods=["GET"])
@cross_domain
@with_session
def native_language():
    """
    Get the native language of the user in session
    :return:
    """
    return flask.g.user.native_language.code


@api.route("/learned_and_native_language", methods=["GET"])
@cross_domain
@with_session
def learned_and_native_language():
    """
    Get the native language of the user in session
    :return:
    """
    u = flask.g.user
    res = dict(native=u.native_language_id,
               learned=u.learned_language_id)
    return json_result(res)


@api.route("/native_language/<language_code>", methods=["POST"])
@cross_domain
@with_session
def native_language_set(language_code):
    """
    set the native language of the user in session
    :param language_code:
    :return: OK for success
    """
    flask.g.user.set_native_language(language_code)
    zeeguu.db.session.commit()
    return "OK"


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
    print(data)

    submitted_name = data.get('name', None)
    if submitted_name:
        flask.g.user.name = submitted_name

    submitted_native_language_code = data.get('native_language_code', None)
    if submitted_native_language_code:
        flask.g.user.set_native_language(submitted_native_language_code)

    submitted_email = data.get('email', None)
    if submitted_email:
        flask.g.user.email = submitted_email

    zeeguu.db.session.commit()
    return "OK"
