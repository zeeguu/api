"""
    Function that captures a pattern that differs only in the name of the class
    between UserExerciseSession and UserReadingSession
"""

import flask
from datetime import datetime

from zeeguu.core.model import User
from zeeguu.core.model.language import Language
from zeeguu.core.model.user_language import UserLanguage


def update_activity_session(session_class, request, db_session):
    form = request.form
    session_id = int(form.get("id", ""))
    duration = int(form.get("duration", 0))

    session = session_class.find_by_id(session_id)
    session.duration = duration
    session.last_action_time = datetime.now()
    db_session.add(session)

    if duration >= MIN_STREAK_DURATION_MS:
        _update_streak(db_session, session)

    db_session.commit()

    return session


MIN_STREAK_DURATION_MS = 120_000  # 2 minutes in milliseconds (frontend sends ms)


def _session_language(session):
    """Return the Language this activity session belongs to, or None.

    The streak must be credited to the language of the *content* the user
    is practicing, not to the user's currently-selected `learned_language`.
    Otherwise, a tail update for a session in language A that arrives after
    the user has switched to language B incorrectly credits B's streak.

    Listening, reading, and watching sessions all carry a content reference
    (daily audio lesson / article / video) that knows its own language.
    Exercise and browsing sessions have no content link, so callers fall
    back to `user.learned_language` for those.
    """
    daily_audio_lesson = getattr(session, "daily_audio_lesson", None)
    if daily_audio_lesson is not None:
        return Language.find_by_id(daily_audio_lesson.language_id)

    article = getattr(session, "article", None)
    if article is not None:
        return Language.find_by_id(article.language_id)

    video = getattr(session, "video", None)
    if video is not None:
        return Language.find_by_id(video.language_id)

    return None


def _update_streak(db_session, session):
    user = User.find_by_id(flask.g.user_id)
    if user is None:
        return

    language = _session_language(session)
    if language is None:
        # Exercise / browsing sessions have no content-derived language;
        # fall back to the user's currently-selected learned_language.
        language = user.learned_language

    if language is None:
        return

    user_language = UserLanguage.find_or_create(db_session, user, language)
    user_language.update_streak_if_needed(db_session)
