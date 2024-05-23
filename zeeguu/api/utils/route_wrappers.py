import functools
import flask
from zeeguu.logging import log
from zeeguu.core.model.session import Session

from datetime import datetime, timedelta
import zeeguu

SESSION_CACHE = {}
SESSION_CACHE_TIMEOUT = 60  # Seconds


def requires_session(view):
    """
    Decorator checks that user is in a session.

    Every API endpoint annotated with @with_session
     expects a session object to be passed as a GET parameter

    Example: API_URL/learned_language?session=123141516
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        try:
            session_uuid = flask.request.args["session"]
            user_id, session_expiry_time = SESSION_CACHE.get(
                session_uuid,
                (
                    None,
                    None,
                ),
            )
            if session_expiry_time is None or datetime.now() > session_expiry_time:
                from zeeguu.api.endpoints.sessions import is_session_valid

                print("----------- Updating Cache! -----------")
                session_object = Session.find(session_uuid)
                if not is_session_valid(session_object):
                    flask.abort(401)
                user_id = session_object.user_id
                SESSION_CACHE[session_uuid] = (
                    user_id,
                    datetime.now() + timedelta(0, SESSION_CACHE_TIMEOUT),
                )
            print("----------- Using Cache! -----------")
            flask.g.user_id = user_id
            flask.g.session_uuid = session_uuid

        except Exception as e:
            import traceback

            traceback.print_exc()
            flask.abort(401)

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
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    return wrapped_view
