import flask
from flask import request, make_response, current_app
from zeeguu.core.model import Session, User
from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.session_helpers import is_session_too_old, force_user_to_relog

from zeeguu.api.utils.route_wrappers import (
    cross_domain,
    requires_session,
    allows_unverified,
    evict_from_session_cache,
)
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
    from zeeguu.logging import log

    log(f"LOGIN ATTEMPT: email='{email}'")
    
    password = request.form.get("password", None)
    if password == "":
        log(f"LOGIN FAILED: email='{email}' - No password provided")
        return make_error(401, "Invalid credentials")

    # Security: Don't reveal whether email exists - use generic error message
    if not User.email_exists(email):
        log(f"LOGIN FAILED: email='{email}' - Email does not exist in database")
        return make_error(401, "Invalid credentials")

    log(f"LOGIN: email='{email}' - Email exists, attempting authorization")
    user = User.authorize(email, password)
    
    if user is None:
        log(f"LOGIN FAILED: email='{email}' - User.authorize() returned None (invalid credentials)")
        return make_error(401, "Invalid credentials")
    
    log(f"LOGIN SUCCESS: email='{email}' - Creating session for user_id={user.id}")
    session = Session.create_for_user(user)
    db_session.add(session)
    db_session.commit()
    resp = make_response({"session": session.uuid})
    # Set secure cookie with proper security flags
    resp.set_cookie(
        "chocolatechip",
        str(session.uuid),
        httponly=True,  # Prevent JavaScript access (XSS protection)
        samesite="Lax",  # CSRF protection
        # HTTPS only, except in local development (DEBUG). Flask always defines
        # SESSION_COOKIE_SECURE, as False, so it can only switch this on.
        secure=current_app.config["SESSION_COOKIE_SECURE"]
        or not current_app.config.get("DEBUG", False),
        max_age=30 * 24 * 60 * 60,  # 30 days
    )
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
    return session.uuid


@api.route("/validate")
@cross_domain
@requires_session
@allows_unverified
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
@allows_unverified
def logout():
    """

    Deactivate a given session.

    """

    # requires_session already took the uuid from the query param or the cookie
    session_uuid = flask.g.session_uuid
    evict_from_session_cache([session_uuid])
    session = Session.find(session_uuid)
    if session is None:
        flask.abort(401)
    db_session.delete(session)
    db_session.commit()

    resp = make_response("OK")
    if request.cookies.get("chocolatechip") == session_uuid:
        resp.delete_cookie("chocolatechip")
    return resp
