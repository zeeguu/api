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
    Decorator checks that user is in a session AND has verified email.

    Every API endpoint annotated with @requires_session expects:
    1. A valid session object passed as a GET parameter or cookie
    2. The user's email to be verified (returns 403 if not)

    Use @allows_unverified after @requires_session for endpoints that
    should work without email verification (e.g., confirm_email, resend_code).

    Example: API_URL/learned_language?session=123141516
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        import sys
        import threading
        import time as time_module
        from zeeguu.api.utils.abort_handling import make_error

        request_start = time_module.time()
        thread_id = threading.current_thread().ident
        # print(f"--> /{view.__name__} [thread={thread_id}] [time={time_module.time()}]")
        sys.stdout.flush()

        try:
            # Check query param first, then fall back to cookie
            session_uuid = flask.request.args.get(
                "session"
            ) or flask.request.cookies.get("chocolatechip")
            if not session_uuid:
                raise KeyError("No session found")

            user_id, session_expiry_time = SESSION_CACHE.get(
                session_uuid,
                (
                    None,
                    None,
                ),
            )
            if session_expiry_time is None or datetime.now() > session_expiry_time:
                from zeeguu.api.utils.session_helpers import (
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
            from zeeguu.core.model import User
            from zeeguu.core.model.user_language import UserLanguage
            from zeeguu.core.model.db import db

            user = User.find_by_id(user_id)

            if user:
                user.update_last_seen_if_needed(db.session)
                # Update per-language streak for the user's current learned language
                if user.learned_language:
                    user_language = UserLanguage.find_or_create(
                        db.session, user, user.learned_language
                    )
                    user_language.update_streak_if_needed(db.session)
                # Commit immediately since this is a simple timestamp update
                db.session.commit()

                # Check email verification (unless endpoint is marked as allowing unverified)
                # Skip for anonymous users - they don't have real emails to verify
                if not getattr(view, '_allows_unverified', False) and not user.is_anonymous() and not user.email_verified:
                    log(f"ACCESS DENIED: user_id={user.id} email not verified for {view.__name__}")
                    return make_error(403, "Please verify your email address first")

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

        # elapsed = time_module.time() - request_start
        # print(f"<-- /{view.__name__} [thread={thread_id}] [elapsed={elapsed:.3f}s]")
        sys.stdout.flush()
        return view(*args, **kwargs)

    return wrapped_view


def allows_unverified(view):
    """
    Decorator marks an endpoint as accessible without email verification.
    Must be used AFTER @requires_session decorator.

    Use for endpoints like:
    - confirm_email (users need to verify their email)
    - resend_verification_code
    - user_details (let users see their status)
    - validate (session validation)
    - logout

    Example:
        @api.route("/confirm_email", methods=["POST"])
        @cross_domain
        @requires_session
        @allows_unverified
        def confirm_email():
            ...
    """
    view._allows_unverified = True
    return view


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


def only_admins(view):
    """
    Decorator checks that user is an admin.
    Must be used after @requires_session decorator.
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        from zeeguu.core.model import User

        user = User.find_by_id(flask.g.user_id)
        if not user or not user.is_admin:
            flask.abort(401)
        return view(*args, **kwargs)

    return wrapped_view


