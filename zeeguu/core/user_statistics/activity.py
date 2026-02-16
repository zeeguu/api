import json

from sqlalchemy import text

import zeeguu.core
from zeeguu.core.constants import SIMPLE_DATE_FORMAT

# Whitelist of allowed table/column combinations for SQL injection prevention
_ALLOWED_ACTIVITY_QUERIES = {
    "user_reading_session": {
        "date_field": "start_time",
        "duration_field": "duration",
    },
    "user_exercise_session": {
        "date_field": "start_time",
        "duration_field": "duration",
    },
}


def reading_duration_by_day(user):
    return _time_by_day(user, "user_reading_session", "start_time", "duration")


def exercises_duration_by_day(user):
    return _time_by_day(user, "user_exercise_session", "start_time", "duration")


def activity_duration_by_day(user):
    return {
        "reading": convert_to_date_seconds(reading_duration_by_day(user)),
        "exercises": convert_to_date_seconds(exercises_duration_by_day(user)),
    }


def convert_to_date_seconds(result_raw):
    result_array = [
        {
            "date": (each._mapping["date"]).strftime(SIMPLE_DATE_FORMAT),
            "seconds": (int(each._mapping["duration"])),
        }
        for each in result_raw
    ]

    return result_array


def _time_by_day(user, table_name, date_field, duration_field):
    # Security: Validate table/column names against whitelist to prevent SQL injection
    if table_name not in _ALLOWED_ACTIVITY_QUERIES:
        raise ValueError(f"Invalid table name: {table_name}")
    allowed = _ALLOWED_ACTIVITY_QUERIES[table_name]
    if date_field != allowed["date_field"] or duration_field != allowed["duration_field"]:
        raise ValueError(f"Invalid column names for table {table_name}")

    # Safe to use string formatting here since values are validated against whitelist
    query = (
        f" SELECT date({date_field}) as date, "
        + f" SUM({duration_field}) / 1000 as duration "
        + f" FROM {table_name}"
        + " WHERE user_id = :uid GROUP BY date;"
    )
    result_raw = zeeguu.core.model.db.session.execute(
        text(query),
        {"uid": user.id},
    )

    return result_raw
