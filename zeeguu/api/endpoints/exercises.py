import traceback
import flask

from zeeguu.core.exercises.similar_words import similar_words
from zeeguu.core.model import Bookmark, User

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.parse_json_boolean import parse_json_boolean
from . import api, db_session
from flask import request

from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule


# ====================================
#  All Scheduled Bookmarks
# ====================================
@api.route("/scheduled_bookmarks", methods=["GET", "POST"])
@cross_domain
@requires_session
def get_scheduled_bookmarks():
    """
    Returns all the words scheduled for learning
    Is used to render the Words>Learning page
    """
    user = User.find_by_id(flask.g.user_id)
    with_tokens = parse_json_boolean(request.form.get("with_tokens", "false"))

    bookmarks = BasicSRSchedule.scheduled_bookmarks(user)

    return _bookmarks_as_json_result(bookmarks, True, with_tokens)


@api.route("/scheduled_bookmarks_count", methods=["GET"])
@cross_domain
@requires_session
def get_scheduled_bookmarks_count():
    user = User.find_by_id(flask.g.user_id)
    bookmark_count = BasicSRSchedule.scheduled_bookmarks_count(user)
    return json_result(bookmark_count)


# ====================================
# Bookmarks due TODAY
# ====================================
@api.route(
    "/bookmarks_scheduled_for_today",
    methods=["GET"],
)
@cross_domain
@requires_session
def bookmarks_scheduled_for_today():
    """
    Returns a number of bookmarks that are scheduled and are due today
    """

    user = User.find_by_id(flask.g.user_id)
    with_tokens = parse_json_boolean(request.form.get("with_context", "false"))
    to_study = BasicSRSchedule.scheduled_bookmarks_due_today(user)

    return _bookmarks_as_json_result(to_study, True, with_tokens)


# ====================================
# Available bookmarks
# ====================================
@api.route("/bookmarks_to_study_count", methods=["GET"])
@cross_domain
@requires_session
def get_bookmarks_to_study_count():
    user = User.find_by_id(flask.g.user_id)
    to_study = BasicSRSchedule.bookmarks_to_study(user)
    return json_result(len(to_study))


@api.route("/bookmarks_to_study", methods=["GET"])
@cross_domain
@requires_session
def get_bookmarks_to_study():
    """
    Return the bookmarks a user has to study
    """
    user = User.find_by_id(flask.g.user_id)
    to_study = BasicSRSchedule.bookmarks_to_study(user)

    return _bookmarks_as_json_result(to_study, True, True)


# ====================================
# Bookmark history
# ====================================


@api.route("/get_exercise_log_for_bookmark/<bookmark_id>", methods=("GET",))
@cross_domain
@requires_session
def get_exercise_log_for_bookmark(bookmark_id):
    bookmark = Bookmark.query.filter_by(id=bookmark_id).first()

    exercise_log_dict = []
    exercise_log = bookmark.exercise_log
    for exercise in exercise_log:
        exercise_log_dict.append(
            dict(
                id=exercise.id,
                outcome=exercise.outcome.outcome,
                source=exercise.source.source,
                exercise_log_solving_speed=exercise.solving_speed,
                time=exercise.time.strftime("%m/%d/%Y"),
            )
        )

    return json_result(exercise_log_dict)


# ====================================
# Uploading exercise info
# ====================================


@api.route(
    "/report_exercise_outcome",
    methods=["POST"],
)
@requires_session
def report_exercise_outcome():
    """
    In the model parlance, an exercise is an entry in a table that
    logs the performance of an exercise. Every such performance, has a source, and an outcome.

    :param exercise_outcome: One of: Correct, Retry, Wrong, Typo, Too easy...
    :param exercise_source: has been assigned to your app by zeeguu
    :param exercise_solving_speed: in milliseconds
    :param bookmark_id: the bookmark for which the data is reported
    :param session_id: assuming that the exercise submitter knows which session is this exercise part of
    :return:
    """

    outcome = request.form.get("outcome", "")
    source = request.form.get("source")
    solving_speed = request.form.get("solving_speed")
    bookmark_id = request.form.get("bookmark_id")
    other_feedback = request.form.get("other_feedback")
    session_id = int(request.form.get("session_id"))

    if not solving_speed.isdigit():
        solving_speed = 0

    try:
        bookmark = Bookmark.find(bookmark_id)
        bookmark.report_exercise_outcome(
            source, outcome, solving_speed, session_id, other_feedback, db_session
        )

        return "OK"
    except:
        traceback.print_exc()
        return "FAIL"


@api.route("/similar_words/<bookmark_id>", methods=["GET"])
@cross_domain
@requires_session
def similar_words_api(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    user = User.find_by_id(flask.g.user_id)
    return json_result(
        similar_words(bookmark.origin.word, bookmark.origin.language, user)
    )


def _bookmarks_as_json_result(bookmarks, with_exercise_info, with_tokens):
    bookmark_dicts = [
        b.as_dictionary(
            with_exercise_info=with_exercise_info, with_context_tokenized=with_tokens
        )
        for b in bookmarks
    ]
    return json_result(bookmark_dicts)
