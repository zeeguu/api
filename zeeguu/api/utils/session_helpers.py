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
