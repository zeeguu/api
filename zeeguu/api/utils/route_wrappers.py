import functools
import flask
from zeeguu.logging import log
from zeeguu.core.model.session import Session
import zeeguu


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
            session_id = int(flask.request.args["session"])
        except:
            flask.abort(401)
        session = Session.query.get(session_id)
        if session is None:
            flask.abort(401)
        flask.g.user = session.user
        session.update_use_date()

        log(str(flask.g.user.id) + " API CALL: " + str(view))

        zeeguu.core.model.db.session.add(session)
        # TODO: remove this commit? and add it after such that the session can be added with the next commit?
        zeeguu.core.model.db.session.commit()
        return view(*args, **kwargs)

        zeeguu.core.model.db.session.close()

    return wrapped_view


def cross_domain(view):
    """
    Decorator enables x-origin requests from any domain.

    More about Cross-Origin Resource Sharing: http://www.w3.org/TR/cors/
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        response = flask.make_response(view(*args, **kwargs))
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    return wrapped_view
