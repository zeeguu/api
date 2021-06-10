import zeeguu_core
from zeeguu_core.sql.learner.exercises_history import exercises_grouped_by_word
from zeeguu_core.user_statistics.exercise_corectness import exercise_outcome_stats
from ._common_api_parameters import _parse__student_id__cohort_id__and__number_of_days
from .. import api, with_session
from ..utils.json_result import json_result

db = zeeguu_core.db


@api.route("/student_exercise_correctness", methods=["POST"])
@with_session
def student_exercise_correctness():
    """
    :return: e.g.
        {
            "Correct": 55,
            "2nd Try": 55,
            "Incorrect": 4,
            "too_easy": 1,
            "Bad Example":1,
        }
    """
    user, cohort, then, now = _parse__student_id__cohort_id__and__number_of_days()
    stats = exercise_outcome_stats(user.id, cohort.id, then, now)
    return json_result(stats)


@api.route("/student_exercise_history", methods=["POST"])
@with_session
def api_student_exercise_history():
    user, cohort, then, now = _parse__student_id__cohort_id__and__number_of_days()
    stats = exercises_grouped_by_word(user.id, cohort.language_id, then, now)
    return json_result(stats)
