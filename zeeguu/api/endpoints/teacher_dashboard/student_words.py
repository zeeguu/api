import zeeguu.core
from zeeguu.core.sql.learner.words import words_not_studied, learned_words
from ._common_api_parameters import _get_student_cohort_and_period_from_POST_params
from .. import api
from zeeguu.api.utils import json_result, with_session

from zeeguu.core.model import db


@api.route("/student_words_not_studied", methods=["POST"])
@with_session
def student_words_not_studied():
    user, cohort, from_str, to_str = _get_student_cohort_and_period_from_POST_params()
    stats = words_not_studied(user.id, cohort.language_id, from_str, to_str)
    return json_result(stats)


@api.route("/student_learned_words", methods=["POST"])
@with_session
def student_learned_words():
    user, cohort, from_date, to_date = _get_student_cohort_and_period_from_POST_params()

    stats = learned_words(user.id, cohort.language_id, from_date, to_date)
    return json_result(stats)
