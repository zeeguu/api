from sqlalchemy import text

import zeeguu.core

from zeeguu.core.model import db
from zeeguu.core.model.cohort import Cohort


def total_time_in_exercise_sessions(user_id, cohort_id, start_time, end_time):
    # TODO: use also the cohort_id somehow
    cohort = Cohort.find(cohort_id)
    query = f"""
        select sum(duration)
        from user_exercise_session as ues
        WHERE ues.id in (SELECT e.session_id from exercise e
                        INNER JOIN bookmark_exercise_mapping bem on e.id = bem.exercise_id
                        INNER JOIN bookmark b ON bem.bookmark_id = b.id
                        INNER JOIN user_word uw ON b.origin_id = uw.id
                        WHERE uw.language_id = {cohort.language_id})
        and ues.start_time > :start_time
        and ues.last_action_time < :end_time
        and ues.user_id = :user_id
    """

    rows = db.session.execute(
        text(query),
        {
            "user_id": user_id,
            "start_time": start_time,
            "end_time": end_time,
        },
    )
    result = rows.first()[0]

    exercise_time_in_sec = 0
    if result:
        exercise_time_in_sec = int(result / 1000)

    return {
        "exercise_time_in_sec": exercise_time_in_sec,
        "exercise_time": exercise_time_in_sec,
    }
