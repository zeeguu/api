"""
    Function that captures a pattern that differs only in the name of the class
    between UserExerciseSession and UserReadingSession
"""

import flask
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound, StaleDataError

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

    # The row can vanish after we read it: deleting a lesson cascades to its
    # listening sessions (and deleting an account to all of a user's sessions),
    # and the client keeps sending updates while that delete runs. The write
    # then matches 0 rows and SQLAlchemy raises StaleDataError. That is the same
    # situation as the session having been gone before we looked, so answer the
    # same 404 instead of a 500. The streak step is inside the try because its
    # queries autoflush this same write.
    try:
        _update_streak(db_session, session)

        db_session.commit()
    except StaleDataError:
        db_session.rollback()
        flask.abort(404)

    return session


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
    user_language = UserLanguage.find_or_create(db_session, user, language)
    if user_language.practiced_today:
        return
    # The day counts once the learner's study time today, across all their
    # sessions in this language, reaches the minimum; this session's update
    # is already in it (the query autoflushes it).
    if user_language.study_ms_today() < UserLanguage.STREAK_MIN_STUDY_MS:
        return
    user_language.update_streak_if_needed(user, db_session)
