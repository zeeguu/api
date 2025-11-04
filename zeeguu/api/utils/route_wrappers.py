import functools
import flask
from werkzeug.exceptions import BadRequestKeyError

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
        import sys
        print("--> /" + view.__name__)
        sys.stdout.flush()

        # Enable SQL query logging for debugging
        import logging
        logging.basicConfig()
        sql_logger = logging.getLogger('sqlalchemy.engine')
        original_level = sql_logger.level
        sql_logger.setLevel(logging.INFO)

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
                from zeeguu.api.endpoints.sessions import (
                    is_session_too_old,
                    force_user_to_relog,
                )

                session_object = Session.find(session_uuid)
                if session_object is None:
                    print("-- Session inexistent")
                    flask.abort(401)
                if is_session_too_old(session_object):
                    print("-- Session is too old")
                    force_user_to_relog(session_object)
                    flask.abort(401)
                user_id = session_object.user_id
                SESSION_CACHE[session_uuid] = (
                    user_id,
                    datetime.now() + timedelta(0, SESSION_CACHE_TIMEOUT),
                )

            flask.g.user_id = user_id
            flask.g.session_uuid = session_uuid

            # Update user's last_seen timestamp (once per day maximum)
            print(f"[SESSION-DEBUG] Loading user {user_id}")
            sys.stdout.flush()
            from zeeguu.core.model import User
            from zeeguu.core.model.db import db
            print(f"[SESSION-DEBUG] About to call User.find_by_id({user_id})")
            sys.stdout.flush()
            user = User.find_by_id(user_id)
            print(f"[SESSION-DEBUG] User loaded: {user.email if user else 'None'}")
            sys.stdout.flush()
            if user:
                print(f"[SESSION-DEBUG] About to call update_last_seen_if_needed()")
                sys.stdout.flush()
                user.update_last_seen_if_needed(db.session)
                print(f"[SESSION-DEBUG] About to commit()")
                sys.stdout.flush()
                # Commit immediately since this is a simple timestamp update
                db.session.commit()
                print(f"[SESSION-DEBUG] Commit completed")
                sys.stdout.flush()
        except BadRequestKeyError as e:
            # This surely happens for missing session key
            # I'm not sure in which way the request could be bad
            # but in any case, we should simply abort if this happens
            print("-- Missing session key, or some other Bad Request Error")
            flask.abort(401)

        except Exception as e:
            import traceback
            from sentry_sdk import capture_exception

            capture_exception(e)
            traceback.print_exc()
            print("-- Some other exception. Aborting")
            flask.abort(401)
        finally:
            # Restore original SQL logging level
            sql_logger.setLevel(original_level)

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
