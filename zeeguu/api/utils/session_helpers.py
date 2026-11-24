from datetime import datetime

import flask

from zeeguu.core.constants import PLATFORM_NAMES
from zeeguu.core.model.db import db

DAYS_BEFORE_EXPIRE = 30  # Days


def platform_from_form():
    """The client's constants.PLATFORM_* code, or None when it sent no valid one."""
    try:
        platform = int(flask.request.form.get("platform", ""))
    except ValueError:
        return None
    return platform if platform in PLATFORM_NAMES else None


# Login sessions already known to have a platform, so the frequent activity
# uploads don't look the session up again on every call.
_SESSIONS_WITH_PLATFORM = set()


def remember_session_platform():
    """
    Give the request's login session its platform, if it has none yet.

    Logins only store their platform since 15 Nov 2026, so older sessions have
    none, and the server events (UserActivityData.log_server_event) logged with
    them get no platform either. A session token stays on one device or browser,
    so the platform the client reports on any request made with it is the
    session's platform: we store the first valid one. Never overwrites a stored
    platform, and ignores PLATFORM_UNKNOWN. Commits only when it stores one.
    """
    from zeeguu.core.constants import PLATFORM_UNKNOWN
    from zeeguu.core.model import Session

    session_uuid = getattr(flask.g, "session_uuid", None)
    if not session_uuid or session_uuid in _SESSIONS_WITH_PLATFORM:
        return
    platform = platform_from_form()
    if platform is None or platform == PLATFORM_UNKNOWN:
        return
    login = Session.find(session_uuid)
    if login is None:
        return
    if login.platform is None:
        login.platform = platform
        db.session.add(login)
        db.session.commit()
    _SESSIONS_WITH_PLATFORM.add(session_uuid)


def is_session_too_old(session_object):
    return (datetime.now() - session_object.last_use).days > DAYS_BEFORE_EXPIRE


def force_user_to_relog(session_object, reason: str = ""):
    print(
        f"Session for user '{session_object.user_id}' was terminated. Reason: '{reason}'"
    )
    db.session.delete(session_object)
    db.session.commit()


def end_other_sessions(user, keep_session_uuid: str = None):
    """
    Log the user out everywhere except keep_session_uuid. Call it whenever the
    password changes. The caller commits.
    """
    from zeeguu.core.model import Session
    from zeeguu.api.utils.route_wrappers import evict_from_session_cache

    ended = Session.delete_all_for_user(user.id, except_uuid=keep_session_uuid)
    evict_from_session_cache(ended)
    return ended
