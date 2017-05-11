import flask
import sqlalchemy
import zeeguu
from flask import request
from zeeguu.model import Session, User

from .utils.route_wrappers import cross_domain, with_session
from . import api


@api.route("/add_user/<email>", methods=["POST"])
@cross_domain
def add_user(email):
    """
   
        Creates user, then redirects to the get_session
        endpoint. Returns a session
        
    """
    password = request.form.get("password")
    username = request.form.get("username")
    if password is None:
        flask.abort(400)
    try:
        zeeguu.db.session.add(User(email, username, password))
        zeeguu.db.session.commit()
    except ValueError:
        flask.abort(400)
    except sqlalchemy.exc.IntegrityError:
        flask.abort(400)
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
    language_code = request.form.get("language_code", None)

    try:
        new_user = User.create_anonymous(uuid, password, language_code)
        zeeguu.db.session.add(new_user)
        zeeguu.db.session.commit()
    except ValueError:
        flask.abort(400)
    except sqlalchemy.exc.IntegrityError:
        flask.abort(400)
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
        flask.abort(400)
    user = User.authorize(email, password)
    if user is None:
        flask.abort(401)
    session = Session.for_user(user)
    zeeguu.db.session.add(session)
    zeeguu.db.session.commit()
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
    zeeguu.db.session.add(session)
    zeeguu.db.session.commit()
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
    zeeguu.db.session.delete(session)
    zeeguu.db.session.commit()

    return "OK"