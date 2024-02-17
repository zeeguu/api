from sqlalchemy import text

import zeeguu.core

from zeeguu.core.model import db


def total_time_in_exercise_sessions(user_id, cohort_id, start_time, end_time):
    # TODO: use also the cohort_id somehow
    query = """
        select sum(duration)
        
        from 
            user_exercise_session as ues
        
        where 
            ues.start_time > :start_time
            and ues.last_action_time < :end_time
            and user_id = :user_id
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
