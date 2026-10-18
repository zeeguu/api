"""
    Function that captures a pattern that differs only in the name of the class
    between UserExerciseSession and UserReadingSession
"""

import flask
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import User
from zeeguu.core.model.user_exercise_session import UserExerciseSession
from zeeguu.core.model.user_language import UserLanguage


def find_own_activity_session(session_class, session_id):
    """
    The session with this id if it belongs to the current user; 404 otherwise.
    A session of another user is answered exactly like a missing one.
    """
    try:
        session = session_class.find_by_id(session_id)
    except NoResultFound:
        flask.abort(404)
    if session.user_id != flask.g.user_id:
        flask.abort(404)
    return session


def update_activity_session(session_class, request, db_session):
    form = request.form
    session_id = int(form.get("id", ""))
    duration = int(form.get("duration", 0))

    session = find_own_activity_session(session_class, session_id)
    if isinstance(session, UserExerciseSession):
        duration = session.capped_duration(
            duration, session.start_time, session.last_answer_time()
        )
    session.duration = duration
    session.last_action_time = datetime.now()
    db_session.add(session)

    if duration >= MIN_STREAK_DURATION_MS:
        _update_streak(db_session, session)

    db_session.commit()

    return session


MIN_STREAK_DURATION_MS = 120_000  # 2 minutes in milliseconds (frontend sends ms)

# Activity sessions belong to a language one of two ways: their content
# (lesson/article/video) carries it, or — for exercise/browsing sessions
# which have no content — they snapshot it at session start. The streak
# must be attributed to *that* language so a tail update arriving after
# the user toggles their learned_language can't be re-credited elsewhere.
_CONTENT_RELATIONSHIPS = ("daily_audio_lesson", "article", "video")


def _session_language(session):
    for attr in _CONTENT_RELATIONSHIPS:
        content = getattr(session, attr, None)
        if content is not None:
            return content.language
    # Snapshot column on UserExerciseSession / UserBrowsingSession.
    # NULL on rows that predate migration 26-04-07.
    return getattr(session, "language", None)


def _update_streak(db_session, session):
    user = User.find_by_id(flask.g.user_id)
    language = _session_language(session) or user.learned_language
    if language is None:
        return
    UserLanguage.find_or_create(db_session, user, language).update_streak_if_needed(user, db_session)
