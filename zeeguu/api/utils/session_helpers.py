from datetime import datetime
from zeeguu.core.model.db import db

DAYS_BEFORE_EXPIRE = 30  # Days


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
