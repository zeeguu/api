"""
    Function that captures a pattern that differs only in the name of the class
    between UserExerciseSession and UserReadingSession
"""

import flask
from datetime import datetime

from zeeguu.core.model import User
from zeeguu.core.model.user_language import UserLanguage


def update_activity_session(session_class, request, db_session):
    form = request.form
    session_id = int(form.get("id", ""))
    duration = int(form.get("duration", 0))

    session = session_class.find_by_id(session_id)
    session.duration = duration
    session.last_action_time = datetime.now()
    db_session.add(session)

    if duration >= MIN_STREAK_DURATION_SECONDS:
        _update_streak(db_session)

    db_session.commit()

    return session


MIN_STREAK_DURATION_SECONDS = 120


def _update_streak(db_session):
    user = User.find_by_id(flask.g.user_id)
    if user and user.learned_language:
        user_language = UserLanguage.find_or_create(
            db_session, user, user.learned_language
        )
        user_language.update_streak_if_needed(db_session)
