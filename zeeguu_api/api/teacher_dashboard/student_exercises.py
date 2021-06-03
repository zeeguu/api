import datetime
from datetime import timedelta

import flask
from dateutil.utils import today
from sqlalchemy.orm.exc import NoResultFound

import zeeguu_core
from zeeguu_core.model import User, Cohort
from zeeguu_core.sql.learner.exercises_history import exercises_grouped_by_word
from zeeguu_core.user_statistics.exercise_corectness import exercise_correctness
from .permissions import (
    check_permission_for_user,
)
from .. import api
from ..utils.json_result import json_result
from ..utils.route_wrappers import with_session

db = zeeguu_core.db


@api.route("/student_exercise_correctness", methods=["POST"])
@with_session
def student_exercise_correctness():
    """
    :param student_id: int
    :param number_of_days: int
    :param cohort_id: int
    :return: e.g.
        {
            "Correct": 55,
            "2nd Try": 55,
            "Incorrect": 4,
            "too_easy": 1,
            "Bad Example":1,
        }
    """
    student_id = flask.request.form.get("student_id")
    number_of_days = flask.request.form.get("number_of_days")
    cohort_id = flask.request.form.get("cohort_id")

    try:
        user = User.query.filter_by(id=student_id).one()
    except NoResultFound:
        flask.abort(400)

    check_permission_for_user(user.id)

    now = today()
    then = now - timedelta(days=int(number_of_days))
    stats = exercise_correctness(user.id, cohort_id, then, now)

    return json_result(stats)


@api.route("/student_exercise_history", methods=["POST"])
@with_session
def api_student_exercise_history():
    student_id = flask.request.form.get("student_id")
    number_of_days = flask.request.form.get("number_of_days")
    cohort_id = flask.request.form.get("cohort_id")

    try:
        user = User.query.filter_by(id=student_id).one()
        cohort = Cohort.find(cohort_id)
    except NoResultFound:
        flask.abort(400)

    check_permission_for_user(user.id)

    now = datetime.datetime.now()
    then = now - timedelta(days=int(number_of_days))
    stats = exercises_grouped_by_word(user.id, cohort.language_id, then, now)
    return json_result(stats)
