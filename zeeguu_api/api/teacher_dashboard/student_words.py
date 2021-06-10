import zeeguu_core
from zeeguu_core.sql.learner.words import words_not_studied, learned_words
from ._common_api_parameters import _parse__student_id__cohort_id__and__number_of_days
from .. import api, json_result, with_session

db = zeeguu_core.db


@api.route("/student_words_not_studied", methods=["POST"])
@with_session
def student_words_not_studied():
    user, cohort, then, now = _parse__student_id__cohort_id__and__number_of_days()
    stats = words_not_studied(user.id, cohort.language_id, then, now)
    return json_result(stats)


@api.route("/student_learned_words", methods=["POST"])
@with_session
def student_learned_words():
    user, cohort, then, now = _parse__student_id__cohort_id__and__number_of_days()
    stats = learned_words(user.id, cohort.language_id, then, now)
    return json_result(stats)
