import datetime
from datetime import timedelta

from dateutil.utils import today

import zeeguu_core

import flask
from flask import jsonify
from sqlalchemy.orm.exc import NoResultFound

from zeeguu_core.model import User, Cohort
from zeeguu_core.user_statistics.exercise_corectness import exercise_correctness
from zeeguu_core.user_statistics.reading_sessions import reading_sessions
from zeeguu_core.user_statistics.student_overview import student_activity_overview
from .decorator import only_teachers
from .helpers import student_info_for_teacher_dashboard
from .permissions import (
    check_permission_for_cohort,
    check_permission_for_user,
)
from .. import api
from ..utils.json_result import json_result
from ..utils.route_wrappers import with_session

db = zeeguu_core.db


@api.route("/user_info/<id>/<duration>", methods=["GET"])
@with_session
def user_info_api(id, duration):

    check_permission_for_user(id)

    return jsonify(student_info_for_teacher_dashboard(id, duration))


@api.route("/cohort_member_bookmarks/<id>/<time_period>", methods=["GET"])
@with_session
@only_teachers
def cohort_member_bookmarks(id, time_period):

    user = User.query.filter_by(id=id).one()

    check_permission_for_cohort(user.cohort_id)

    now = datetime.today()
    date = now - timedelta(days=int(time_period))

    cohort_language_id = Cohort.query.filter_by(id=user.cohort_id).one().language_id

    # True input causes function to return context too.
    return json_result(
        user.bookmarks_by_day(
            True, date, with_title=True, max=10000, language_id=cohort_language_id
        )
    )


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


@api.route("/student_activity_overview", methods=["POST"])
@with_session
def api_student_activity_overview():
    """
    :param student_id: int
    :param number_of_days: int
    :param cohort_id: int
    :return: e.g.

        {
            "number_of_texts": 3,
            "reading_time": 325,
            "average_text_length": 245,
            "average_text_difficulty": 41,
            "exercise_time_in_sec": 818,
            "Correct_on_1st_Try": 87
        }
    """
    student_id = flask.request.form.get("student_id")
    number_of_days = flask.request.form.get("number_of_days")
    cohort_id = flask.request.form.get("cohort_id")

    try:
        user = User.query.filter_by(id=student_id).one()
    except NoResultFound:
        flask.abort(400)

    # check_permission_for_user(user.id)

    now = today()
    then = now - timedelta(days=int(number_of_days))
    stats = student_activity_overview(user.id, cohort_id, then, now)

    return json_result(stats)


@api.route("/student_reading_sessions", methods=["POST"])
@with_session
def student_reading_sessions():
    """
    :param student_id: int
    :param number_of_days: int
    :param cohort_id: int
    :return: Example output
        [
            {
                "session_id": 52719,
                "user_id": 534,
                "start_time": "2021-04-26T18:45:18",
                "end_time": "2021-04-26T18:48:01",
                "duration_in_sec": 163,
                "article_id": 1505738,
                "title": "Dieter Henrichs Autobiographie: Das Ich, das viel besagt",
                "word_count": 490,
                "difficulty": 54,
                "language_id": 3,
                "translations": []
            },
            {
                "session_id": 52665,
                "user_id": 534,
                "start_time": "2021-04-17T15:20:09",
                "end_time": "2021-04-17T15:22:43",
                "duration_in_sec": 154,
                "article_id": 1504732,
                "title": "Interview mit Swiss Re-Chef",
                "word_count": 134,
                "difficulty": 40,
                "language_id": 3,
                "translations": [
                    {
                        "id": 279611,
                        "word": "Zugang",
                        "translation": "Access",
                        "context": " Re-Chef: „Der Zugang zur EU ",
                        "practiced": 1
                    },
                    {
                        "id": 279612,
                        "word": "Verwaltungsratspräsident",
                        "translation": "Chairman of the Board of Directors",
                        "context": " Der Verwaltungsratspräsident des Versicherers ",
                        "practiced": 0
                    }
                ]
            }
        ]
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
    sessions = reading_sessions(user.id, cohort_id, then, now)

    return json_result(sessions)


@api.route("/join_cohort", methods=["POST"])
@with_session
def join_cohort():

    invite_code = flask.request.form.get("invite_code")

    cohort = Cohort.find_by_code(invite_code)
    flask.g.user.cohort_id = cohort.id

    db.session.add(flask.g.user)
    db.session.commit()

    return "OK"


# deprecated
# use student_reading_sessions
@api.route("/cohort_member_reading_sessions/<id>/<time_period>", methods=["GET"])
@with_session
def cohort_member_reading_sessions(id, time_period):
    """
    Returns reading sessions from member with input user id.
    """
    try:
        user = User.query.filter_by(id=id).one()
    except NoResultFound:
        flask.abort(400)
        return "NoUserFound"

    check_permission_for_cohort(user.cohort_id)

    cohort = Cohort.query.filter_by(id=user.cohort_id).one()
    cohort_language_id = cohort.language_id

    now = today()
    date = now - timedelta(days=int(time_period))
    return json_result(
        user.reading_sessions_by_day(date, max=10000, language_id=cohort_language_id)
    )
