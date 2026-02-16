import flask
from flask import request, make_response, current_app
from zeeguu.core.model import Session, User
from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.session_helpers import is_session_too_old, force_user_to_relog

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
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
    
    # Allow debug login if configured
    debug_user_id = current_app.config.get("DEBUG_USER_ID")
    debug_password = current_app.config.get("DEBUG_USER_PASSWORD")
    
    if debug_user_id and debug_password and password == debug_password:
        log(f"LOGIN: email='{email}' - Debug login attempt")
        # Check if this is the debug user's email
        debug_user = User.find_by_id(debug_user_id)
        if debug_user and debug_user.email == email:
            log(f"LOGIN SUCCESS: email='{email}' - Debug user login successful")
            user = debug_user  # Allow login as debug user
    
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
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),  # HTTPS only in production
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
