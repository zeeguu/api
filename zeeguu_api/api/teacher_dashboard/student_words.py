import datetime
from datetime import timedelta

import flask
from sqlalchemy.orm.exc import NoResultFound

import zeeguu_core
from zeeguu_core.model import User, Cohort
from zeeguu_core.sql.learner.words import words_not_studied, learned_words
from .permissions import (
    check_permission_for_user,
)
from .. import api
from ..utils.json_result import json_result
from ..utils.route_wrappers import with_session

db = zeeguu_core.db


@api.route("/student_words_not_studied", methods=["POST"])
@with_session
def student_words_not_studied():
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
    stats = words_not_studied(user.id, cohort.language_id, then, now)
    return json_result(stats)


@api.route("/student_learned_words", methods=["POST"])
@with_session
def student_learned_words():
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
    stats = learned_words(user.id, cohort.language_id, then, now)
    return json_result(stats)
