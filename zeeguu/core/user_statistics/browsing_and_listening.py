"""
Browsing the article list and listening to audio lessons, in a class's
language: the two kinds of activity the teacher's class list used to leave
out. Seconds, like reading_time and exercise_time beside them.
"""

from sqlalchemy import text

from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model.db import db


def _seconds(query, params):
    total = db.session.execute(text(query), params).first()[0]
    return int(total / 1000) if total else 0


def browsing_and_listening_time(user_id, cohort_id, start_time, end_time):
    language_id = Cohort.find(cohort_id).language_id
    params = {
        "user_id": user_id,
        "language_id": language_id,
        "start_time": start_time,
        "end_time": end_time,
    }

    # language_id on a browsing session: the learned language when it started
    browsing = _seconds(
        """
        select sum(duration) from user_browsing_session
        where user_id = :user_id
          and language_id = :language_id
          and start_time > :start_time
          and start_time < :end_time
        """,
        params,
    )

    listening = _seconds(
        """
        select sum(uls.duration)
        from user_listening_session as uls
        join daily_audio_lesson as dal on dal.id = uls.daily_audio_lesson_id
        where uls.user_id = :user_id
          and dal.language_id = :language_id
          and uls.start_time > :start_time
          and uls.start_time < :end_time
        """,
        params,
    )

    return {"browsing_time": browsing, "audio_time": listening}
