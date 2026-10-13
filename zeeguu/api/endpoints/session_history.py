"""
Session-based history API endpoints.

Provides a chronological view of user learning activities organized by session type:
- Reading sessions: time spent reading articles with translations
- Exercise sessions: practice time with performance metrics
- Browsing sessions: time spent browsing article lists
- Audio sessions: listening to daily audio lessons
"""

import flask
from datetime import datetime, timedelta

from . import api
from zeeguu.api.utils import requires_session, json_result
from zeeguu.core.model import User
from zeeguu.core.user_statistics.session_history import session_history


def _parse_iso(date_str):
    return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)


def date_range_from_request():
    """
    Either from_date + to_date (ISO), or days back from now (default 7).
    """
    from_date_str = flask.request.args.get("from_date")
    to_date_str = flask.request.args.get("to_date")

    if from_date_str and to_date_str:
        try:
            return _parse_iso(from_date_str), _parse_iso(to_date_str)
        except ValueError:
            flask.abort(400)

    try:
        days = int(flask.request.args.get("days", 7))
        to_date = datetime.now()
        return to_date - timedelta(days=days), to_date
    except (ValueError, OverflowError):
        flask.abort(400)


@api.route("/session_history", methods=["GET"])
@requires_session
def session_history_api():
    """
    Session-based history for the current user, in their learned language.

    Query params:
        days: number of days to look back (default: 7)
        from_date: ISO date string for custom range start
        to_date: ISO date string for custom range end

    Returns a list of sessions ordered by start_time descending. Each session includes:
        - session_type: 'reading', 'exercise', 'browsing' or 'audio'
        - start_time: ISO timestamp
        - duration: in milliseconds
        - words: list of words translated/practiced
        - For reading: article title, word count and difficulty
        - For exercise: performance summary
    """
    user = User.find_by_id(flask.g.user_id)
    from_date, to_date = date_range_from_request()

    return json_result(
        session_history(user.id, user.learned_language.id, from_date, to_date)
    )
