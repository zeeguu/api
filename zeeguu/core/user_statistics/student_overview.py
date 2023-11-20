import zeeguu.core
from .exercise_corectness import (
    exercise_count_and_correctness_percentage,
    number_of_distinct_words_in_exercises,
    number_of_words_translated_but_not_studied,
    number_of_learned_words,
)
from .exercise_sessions import total_time_in_exercise_sessions
from .reading_sessions import summarize_reading_activity

from zeeguu.core.model import db


def student_activity_overview(user_id, cohort_id, start_date: str, end_date: str):

    student_activity = {}

    student_activity.update(
        summarize_reading_activity(user_id, cohort_id, start_date, end_date)
    )

    student_activity.update(
        total_time_in_exercise_sessions(user_id, cohort_id, start_date, end_date)
    )

    student_activity.update(
        exercise_count_and_correctness_percentage(
            user_id, cohort_id, start_date, end_date
        )
    )

    student_activity.update(
        number_of_distinct_words_in_exercises(user_id, cohort_id, start_date, end_date)
    )

    student_activity.update(
        number_of_words_translated_but_not_studied(
            user_id, cohort_id, start_date, end_date
        )
    )

    student_activity.update(
        number_of_learned_words(user_id, cohort_id, start_date, end_date)
    )

    return student_activity
