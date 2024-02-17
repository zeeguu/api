import json

from sqlalchemy import text

import zeeguu.core
from zeeguu.core.constants import SIMPLE_DATE_FORMAT


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
    query = (
            f" SELECT date({date_field}) as date, "
            + f" SUM({duration_field}) / 1000 as duration "
            + f" FROM {table_name}"
            + " WHERE user_id = :uid GROUP BY date;"
    )
    result_raw = zeeguu.core.model.db.session.execute(
        text(query),
        {"uid": user.id, "table_name": table_name},
    )

    return result_raw
