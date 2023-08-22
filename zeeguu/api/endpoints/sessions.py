import flask
from flask import request, make_response
from zeeguu.core.model import Session, User
from zeeguu.api.utils.abort_handling import make_error

from zeeguu.api.utils.route_wrappers import cross_domain, with_session
from . import api, db_session


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
    session = Session.for_user(user)
    db_session.add(session)
    db_session.commit()
    resp = make_response(str(session.id))
    resp.set_cookie("chocolatechip", str(session.id))
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
    session = Session.for_user(user)
    db_session.add(session)
    db_session.commit()
    return str(session.id)


@api.route("/validate")
@cross_domain
@with_session
def validate():
    """

        If your session is valid, you will get an OK.
        Use this one to test that you are holding a
        valid session.

    :return:
    """
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
@with_session
def logout():
    """

    Deactivate a given session.

    """

    try:
        session_id = int(request.args["session"])
    except:
        flask.abort(401)
    session = Session.query.get(session_id)

    # print "about to expire session..." + str(session_id)
    db_session.delete(session)
    db_session.commit()

    return "OK"
