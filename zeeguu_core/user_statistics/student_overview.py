import zeeguu_core
from .exercise_corectness import correctness_percentage
from .exercise_sessions import total_time_in_exercise_sessions
from .reading_sessions import summarize_reading_activity

db = zeeguu_core.db


def student_activity_overview(user_id, cohort_id, start_date, end_date):

    student_activity = {}
    student_activity.update(
        summarize_reading_activity(user_id, cohort_id, start_date, end_date)
    )

    student_activity.update(
        total_time_in_exercise_sessions(user_id, cohort_id, start_date, end_date)
    )

    student_activity.update(
        correctness_percentage(user_id, cohort_id, start_date, end_date)
    )

    return student_activity
