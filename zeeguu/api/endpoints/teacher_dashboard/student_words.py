import zeeguu.core
import flask
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import User, Cohort
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.phrase import Phrase
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.util.encoding import datetime_to_json
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from ._permissions import check_permission_for_user
from ..bookmarks_and_words import learned_user_words_as_dicts
from ..exercises import user_words_as_dicts
from zeeguu.core.sql.learner.words import words_not_studied, learned_words
from ._common_api_parameters import _get_student_cohort_and_period_from_POST_params
from .. import api
from zeeguu.api.utils import json_result, requires_session

from zeeguu.core.model.db import db


@api.route("/student_words_not_studied", methods=["POST"])
@requires_session
def student_words_not_studied():
    user, cohort, from_str, to_str = _get_student_cohort_and_period_from_POST_params()
    stats = words_not_studied(user.id, cohort.language_id, from_str, to_str)
    return json_result(stats)


@api.route("/student_learned_words", methods=["POST"])
@requires_session
def student_learned_words():
    user, cohort, from_date, to_date = _get_student_cohort_and_period_from_POST_params()

    stats = learned_words(user.id, cohort.language_id, from_date, to_date)
    return json_result(stats)


# ---------------------------------------------------------------------------
# The student's own Words pages (Learning, Learned), for their teacher.
# ---------------------------------------------------------------------------

LEARNED_SHOWN = 300  # as many as the learner's own Learned page asks for
EXCLUDED_SHOWN = 200


def _excluded_user_words(student, language_id):
    """Translated, not learned, and left out of exercises: by the algorithm
    (a bad example, a name, too common...) or because the student said so."""
    return (
        UserWord.query.join(Meaning, UserWord.meaning_id == Meaning.id)
        .join(Phrase, Meaning.origin_id == Phrase.id)
        .filter(UserWord.user_id == student.id)
        .filter(Phrase.language_id == language_id)
        .filter(UserWord.learned_time == None)  # noqa: E711
        .filter((UserWord.fit_for_study == None) | (UserWord.fit_for_study != 1))  # noqa: E711
        .order_by(UserWord.id.desc())
        .limit(EXCLUDED_SHOWN)
        .all()
    )


def _with_attempts(word_dicts):
    """Each word's exercise attempts, oldest first: when, the outcome, and
    which kind of exercise. One query for all the words."""
    ids = [w["user_word_id"] for w in word_dicts if w.get("user_word_id")]
    attempts = {}
    if ids:
        exercises = (
            Exercise.query.options(joinedload(Exercise.outcome), joinedload(Exercise.source))
            .filter(Exercise.user_word_id.in_(ids))
            .order_by(Exercise.time)
            .all()
        )
        for e in exercises:
            attempts.setdefault(e.user_word_id, []).append(
                {
                    "time": datetime_to_json(e.time),
                    "outcome": e.outcome.outcome if e.outcome else None,
                    "source": e.source.source if e.source else None,
                }
            )
    for w in word_dicts:
        w["exercise_attempts"] = attempts.get(w.get("user_word_id"), [])
    return word_dicts


@api.route("/student_word_lists", methods=["GET"])
@requires_session
def student_word_lists():
    """
    What a student sees on their own Words pages, in the class's language, for
    their teacher: scheduled (Learning), next in exercises, excluded from
    exercises, learned. Words carry their exercise attempts.

    Query params: student_id, cohort_id.
    """
    try:
        cohort = Cohort.find(flask.request.args["cohort_id"])
        student = User.query.filter_by(id=flask.request.args["student_id"]).one()
    except (KeyError, NoResultFound):
        flask.abort(400)
    check_permission_for_user(student.id, cohort.id)

    language_id = cohort.language_id
    scheduled = BasicSRSchedule.scheduled_user_words(student, cohort.language)
    next_in_learning = BasicSRSchedule.user_words_not_scheduled(student, 6, language_id)

    return json_result(
        {
            "scheduled": _with_attempts(user_words_as_dicts(scheduled)),
            "next_in_learning": _with_attempts(user_words_as_dicts(next_in_learning)),
            "excluded": _with_attempts(user_words_as_dicts(_excluded_user_words(student, language_id))),
            "learned": _with_attempts(learned_user_words_as_dicts(student, LEARNED_SHOWN, language_id)),
            "total_learned": student.total_learned_user_words(language_id),
        }
    )
