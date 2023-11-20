import zeeguu.core
from zeeguu.core.sql.learner.exercises_history import exercises_grouped_by_word
from zeeguu.core.user_statistics.exercise_corectness import exercise_outcome_stats
from ._common_api_parameters import (
    _get_student_cohort_and_period_from_POST_params,
)
from .. import api
from zeeguu.api.utils import json_result, with_session

from zeeguu.core.model import db


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
    user, cohort, from_date, to_date = _get_student_cohort_and_period_from_POST_params()

    stats = exercise_outcome_stats(user.id, cohort.id, from_date, to_date)
    return json_result(stats)


@api.route("/student_exercise_history", methods=["POST"])
@with_session
def api_student_exercise_history():
    user, cohort, from_date, to_date = _get_student_cohort_and_period_from_POST_params()
    stats = exercises_grouped_by_word(user.id, cohort.language_id, from_date, to_date)
    return json_result(stats)
