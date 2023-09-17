import zeeguu.core
from zeeguu.core.user_statistics.student_overview import student_activity_overview
from ._common_api_parameters import _get_student_cohort_and_period_from_POST_params
from .. import api
from zeeguu.api.utils import json_result, with_session


from zeeguu.core.model import db


@api.route("/student_activity_overview", methods=["POST"])
@with_session
def api_student_activity_overview():
    """
    :param student_id: int
    :param number_of_days: int
    :param cohort_id: int
    :return: e.g.

        {
            "number_of_texts": 13,
            "reading_time": 5679,
            "average_text_length": 394,
            "average_text_difficulty": 44,
            "exercise_time_in_sec": 664,
            "correct_on_1st_try": 0.64,
            "number_of_exercises": 59,
            "practiced_words_count": 40
            "translated_but_not_practiced_words_count": 163,
            "learned_words_count": 0
        }
    """
    user, cohort, from_date, to_date = _get_student_cohort_and_period_from_POST_params()
    stats = student_activity_overview(user.id, cohort.id, from_date, to_date)

    return json_result(stats)
