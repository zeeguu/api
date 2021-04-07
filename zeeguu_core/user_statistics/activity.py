import json

import zeeguu_core
from zeeguu_core.constants import SIMPLE_DATE_FORMAT


def reading_duration_by_day(user):
    return _time_by_day(user, "user_reading_session")


def exercises_duration_by_day(user):
    return _time_by_day(user, "user_exercise_session")


def activity_duration_by_day(user):
    return {
        "reading": reading_duration_by_day(user),
        "exercises": exercises_duration_by_day(user),
    }


def _time_by_day(user, table_name):
    query = (
        " SELECT date(start_time) as date, "
        + " SUM(duration) / 1000 as duration "
        + f" FROM {table_name}"
        + " WHERE user_id = :uid GROUP BY date;"
    )
    result_raw = zeeguu_core.db.session.execute(
        query,
        {"uid": user.id, "table_name": table_name},
    )

    result_array = [
        {
            "date": (each["date"]).strftime(SIMPLE_DATE_FORMAT),
            "seconds": (int(each["duration"])),
        }
        for each in result_raw
    ]

    return result_array
