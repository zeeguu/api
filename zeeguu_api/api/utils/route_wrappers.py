import functools
import flask
import zeeguu
from zeeguu.model.session import Session
from zeeguu import db

def with_session(view):
    """
    Decorator checks that user is in a session.

    Every API endpoint annotated with @with_session
     expects a session object to be passed as a GET parameter

    Example: API_URL/learned_language?session=123141516
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        try:
            session_id = int(flask.request.args['session'])
            zeeguu.log(("API CALL: " + str(view)))
        except:
            flask.abort(401)
        session = Session.query.get(session_id)
        if session is None:
            flask.abort(401)
        flask.g.user = session.user
        session.update_use_date()

        db.session.add(session)
        db.session.commit()
        return view(*args, **kwargs)

    return wrapped_view


def cross_domain(view):
    """
    Decorator enables x-origin requests from any domain.

    More about Cross-Origin Resource Sharing: http://www.w3.org/TR/cors/
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        response = flask.make_response(view(*args, **kwargs))
        response.headers['Access-Control-Allow-Origin'] = "*"
        return response

    return wrapped_view
