import flask
from datetime import datetime
from flask import request, make_response
from zeeguu.core.model.session import Session
from zeeguu.core.model.user import User
from zeeguu.api.utils.abort_handling import make_error

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api, db_session

DAYS_BEFORE_EXPIRE = 30  # Days


def is_session_too_old(session_object):
    return (datetime.now() - session_object.last_use).days > DAYS_BEFORE_EXPIRE


def force_user_to_relog(session_object, reason: str = ""):
    print(
        f"Session for user '{session_object.user_id}' was terminated. Reason: '{reason}'"
    )
    db_session.delete(session_object)
    db_session.commit()


@api.route("/session/<email>", methods=["POST"])
@cross_domain
def get_session(email):
    """
    If the email and password match,
    a sessionId is returned as a string.
    This sessionId can to be passed
    along all the other requests that are annotated
    with @with_user in this file
    """

    password = request.form.get("password", None)
    if password == "":
        return make_error(401, "Password not given")

    if not User.email_exists(email):
        return make_error(401, "There is no account associated with this email")

    user = User.authorize(email, password)
    if user is None:
        return make_error(401, "Invalid credentials")
    session = Session.create_for_user(user)
    db_session.add(session)
    db_session.commit()
    resp = make_response({"session": session.uuid})
    resp.set_cookie("chocolatechip", str(session.uuid))
    return resp


@api.route("/get_anon_session/<uuid>", methods=["POST"])
@cross_domain
def get_anon_session(uuid):
    """

    If the uuid and password match, a  sessionId is
    returned as a string. This sessionId can to be passed
    along all the other requests that are annotated
    with @with_user in this file

    """
    password = request.form.get("password", None)

    if password is None:
        flask.abort(400)
    user = User.authorize_anonymous(uuid, password)
    if user is None:
        flask.abort(401)
    session = Session.create_for_user(user)
    db_session.add(session)
    db_session.commit()
    return str(session.id)


@api.route("/validate")
@cross_domain
@requires_session
def validate():
    """

        If your session is valid, you will get an OK.
        Use this one to test that you are holding a
        valid session.

    :return:
    """
    # TODO: ideally update in parallel with running the decorated method?
    session_object = Session.find(flask.g.session_uuid)
    if session_object is None:
        flask.abort(401)
    if is_session_too_old(session_object):
        force_user_to_relog(session_object, "Session was too old.")
        flask.abort(401)
    session_object.update_use_date()
    db_session.add(session_object)
    db_session.commit()
    return "OK"


@cross_domain
@api.route("/is_up")
def is_up():
    """

        Useful for testing that the server is up

    :return:
    """
    return "OK"


@api.route("/logout_session", methods=["GET"])
@cross_domain
@requires_session
def logout():
    """

    Deactivate a given session.

    """

    try:
        session_uuid = request.args["session"]
        session = Session.find(session_uuid)
        db_session.delete(session)
        db_session.commit()
    except:
        flask.abort(401)

    return "OK"
