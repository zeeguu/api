from datetime import datetime
from typing import Callable, Optional

import flask
from flask import request

from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.leaderboards.leaderboards import exercise_time_leaderboard, exercises_done_leaderboard, \
    read_articles_leaderboard, reading_time_leaderboard, listening_time_leaderboard
from . import api

LeaderboardMetric = Callable[[int, int, Optional[datetime], Optional[datetime]], list]

LEADERBOARD_METRICS: dict[str, LeaderboardMetric] = {
    "exercise_time": exercise_time_leaderboard,
    "exercises_done": exercises_done_leaderboard,
    "read_articles": read_articles_leaderboard,
    "reading_time": reading_time_leaderboard,
    "listening_time": listening_time_leaderboard,
}


# ---------------------------------------------------------------------------
@api.route("/friends_leaderboard", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def friends_leaderboard():
    params, error_response = _parse_leaderboard_query_params()
    if error_response:
        return error_response

    metric = LEADERBOARD_METRICS.get(request.args.get("metric"))

    if not metric:
        return make_error(400, "Invalid leaderboard metric")

    rows = metric(
        flask.g.user_id,
        params["limit"],
        params["from_date"],
        params["to_date"],
    )

    result = [
        _serialize_leaderboard_row(row)
        for row in rows
    ]

    return json_result(result)


# ---------------------------------------------------------------------------
# Helper functions below
# ---------------------------------------------------------------------------

def _parse_leaderboard_query_params():
    """
    Parse common leaderboard query params:
        limit: positive integer
        from_date: ISO datetime string (optional)
        to_date: ISO datetime string (optional)
    """
    limit = 20
    limit_arg = request.args.get("limit")
    if limit_arg is not None:
        try:
            limit = int(limit_arg)
        except ValueError:
            return None, make_error(400, "limit must be an integer")

        if limit <= 0:
            return None, make_error(400, "limit must be greater than 0")

    from_date_str = request.args.get("from_date")
    to_date_str = request.args.get("to_date")

    from_date = None
    to_date = None

    if from_date_str:
        from_date, error = _parse_iso_datetime(from_date_str, "from_date")
        if error:
            return None, error

    if to_date_str:
        to_date, error = _parse_iso_datetime(to_date_str, "to_date")
        if error:
            return None, error

    if from_date and to_date and from_date > to_date:
        return None, make_error(400, "from_date must be before or equal to to_date")

    return {
        "limit": limit,
        "from_date": from_date,
        "to_date": to_date,
    }, None


def _parse_iso_datetime(value: str, param_name: str):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        return parsed, None
    except ValueError:
        return None, make_error(400, f"{param_name} must be a valid ISO datetime")


def _serialize_leaderboard_row(row):
    return {
        "user": {
            "name": row.name,
            "username": row.username,
            "avatar": {
                "image_name": row.image_name,
                "character_color": row.character_color,
                "background_color": row.background_color,
            }
        },
        "value": row.value,
    }
