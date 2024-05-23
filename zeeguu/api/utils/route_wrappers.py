import functools
import flask
from zeeguu.logging import log
from zeeguu.core.model.session import Session, User
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
            session_uuid = flask.request.args["session"]
            session_object = Session.find(session_uuid)
            if session_object is None:
                flask.abort(401)

            user = User.find_by_id(session_object.user_id)
            flask.g.user = user
            # TODO: ideally update in parallel with running the decorated method?
            session_object.update_use_date()
            zeeguu.core.model.db.session.add(session_object)
            zeeguu.core.model.db.session.commit()

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
