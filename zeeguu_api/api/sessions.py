import flask
import sqlalchemy
import zeeguu
from flask import request
from zeeguu.model import Session, User
from zeeguu.model.unique_code import UniqueCode
from zeeguu_api.api.utils.abort_handling import make_error
from zeeguu_api.api.utils.reset_password import send_password_reset_email

from .utils.route_wrappers import cross_domain, with_session
from . import api, db_session


@api.route("/add_user/<email>", methods=["POST"])
@cross_domain
def add_user(email):
    """
   
        Creates user, then redirects to the get_session
        endpoint. Returns a session
        
    """
    password = request.form.get("password")
    username = request.form.get("username")
    if password is None or len(password) < 4:
        return make_error(400, "Password should be at least 4 characters long")
    try:
        db_session.add(User(email, username, password))
        db_session.commit()
    except ValueError:
        return make_error(400, "Invalid value")
    except sqlalchemy.exc.IntegrityError:
        return make_error(401, "There is already an account for this email.")
    return get_session(email)


@api.route("/add_anon_user", methods=["POST"])
@cross_domain
def add_anon_user():
    """
    
        Creates anonymous user, then redirects to the get_session
        endpoint. Returns a session
        
    """

    # These two are post parameters required by the method
    uuid = request.form.get("uuid", None)
    password = request.form.get("password", None)

    # These two are optional
    language_code = request.form.get("learned_language_code", None)
    native_code = request.form.get("native_language_code", None)

    try:
        new_user = User.create_anonymous(uuid, password, language_code, native_code)
        db_session.add(new_user)
        db_session.commit()
    except ValueError as e:
        flask.abort(flask.make_response("Could not create anon user.", 400))
    except sqlalchemy.exc.IntegrityError as e:
        flask.abort(flask.make_response("Could not create anon user. Maybe uuid already exists?", 400))
    return get_anon_session(uuid)


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
    if password is None:
        return make_error(400, "Password not given")
    user = User.authorize(email, password)
    if user is None:
        return make_error(401, "Invalid credentials")
    session = Session.for_user(user)
    db_session.add(session)
    db_session.commit()
    return str(session.id)


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


@api.route("/send_code/<email>", methods=["POST"])
@cross_domain
def send_code(email):
    """
    This endpoint generates a unique code that will be used to allow
    the user to change his/her password. The unique code is send to
    the specified email address.
    """
    code = UniqueCode(email)
    db_session.add(code)
    db_session.commit()

    send_password_reset_email(email, code)

    return "OK"


@api.route("/reset_password/<email>", methods=["POST"])
@cross_domain
def reset_password(email):
    """
    This endpoint can be used to rest a users password.
    To do this a uniquecode is required.
    """
    last_code = UniqueCode.last_code(email)
    code = request.form.get("code", None)
    if not (last_code == code):
        return make_error(400, "Invalid code")

    password = request.form.get("password", None)
    if len(password) < 4:
        return make_error(400, "Password should be at least 4 characters long")

    user = User.find(email)
    if user is None:
        return make_error(400, "Email unknown")
    user.update_password(password)
    db_session.commit()

    # Delete all the codes for this user
    for x in UniqueCode.all_codes_for(email):
        db_session.delete(x)
    db_session.commit()

    return "OK"


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


@api.route("/logout_session",
           methods=["GET"])
@cross_domain
@with_session
def logout():
    """
    
        Deactivate a given session. 
    
    """

    try:
        session_id = int(request.args['session'])
    except:
        flask.abort(401)
    session = Session.query.get(session_id)

    # print "about to expire session..." + str(session_id)
    db_session.delete(session)
    db_session.commit()

    return "OK"
