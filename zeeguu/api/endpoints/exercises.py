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


@api.route(
    "/bookmarks_scheduled_for_today/<bookmark_count>",
    methods=["GET", "POST"],
)
@cross_domain
@requires_session
def bookmarks_scheduled_for_today(bookmark_count):
    """
    Returns a number of <bookmark_count> bookmarks that
    are in the pipeline and are due today

    """
    int_count = int(bookmark_count)
    user = User.find_by_id(flask.g.user_id)
    with_token = parse_json_boolean(request.form.get("with_context", "false"))
    to_study = BasicSRSchedule.scheduled_bookmarks_due_today(user, int_count)
    json_bookmarks = [
        bookmark.as_dictionary(
            with_exercise_info=True, with_context_tokenized=with_token
        )
        for bookmark in to_study
    ]
    return json_result(json_bookmarks)


@api.route("/all_bookmarks_available_for_study_count", methods=["GET"])
@cross_domain
@requires_session
def bookmarks_available_for_study_count():
    """
    Return the number of bookmarks the user has available to study (both in pipeline and
    not started yet). Can be used to determine how many bookmarks we should pull for
    the exercises.
    """
    user = User.find_by_id(flask.g.user_id)
    to_study = BasicSRSchedule.all_bookmarks_available_prioritized(user)
    return json_result(len(to_study))


@api.route("/all_bookmarks_available_for_study/<bookmark_count>", methods=["GET"])
@cross_domain
@requires_session
def bookmarks_available_for_study(bookmark_count):
    """
    Return all the possible bookmarks a user has to study ordered by
    how common it is in the language and how close they are to being learned.
    """
    int_count = int(bookmark_count)
    user = User.find_by_id(flask.g.user_id)

    to_study = BasicSRSchedule.all_bookmarks_available_prioritized(user, int_count)

    json_bookmarks = [
        bookmark.as_dictionary(with_exercise_info=True, with_context_tokenized=True)
        for bookmark in to_study
    ]
    return json_result(json_bookmarks)


@api.route("/bookmarks_to_learn_not_scheduled", methods=["GET", "POST"])
@cross_domain
@requires_session
def bookmarks_to_learn_not_scheduled():
    """
    Return all the bookmarks that aren't learned and haven't been
    scheduled to the user.
    """
    user = User.find_by_id(flask.g.user_id)
    with_tokens = parse_json_boolean(request.form.get("with_tokens", "false"))
    to_study = user.bookmarks_to_learn_not_in_pipeline()
    json_bookmarks = [
        bookmark.as_dictionary(
            with_exercise_info=True, with_context_tokenized=with_tokens
        )
        for bookmark in to_study
    ]

    return json_result(json_bookmarks)


@api.route("/bookmarks_in_pipeline", methods=["GET", "POST"])
@cross_domain
@requires_session
def bookmarks_in_pipeline(with_tokens=None):
    """
    Returns all the words in the pipeline to be learned by a user.
    Is used to render the Words tab in Zeeguu
    """
    user = User.find_by_id(flask.g.user_id)
    with_tokens = parse_json_boolean(request.form.get("with_tokens", "false"))

    from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

    bookmarks = BasicSRSchedule.scheduled_bookmarks(user)
    bookmark_dicts = [
        b.as_dictionary(with_exercise_info=True, with_context_tokenized=with_tokens)
        for b in bookmarks
    ]
    return json_result(bookmark_dicts)


@api.route("/new_bookmarks_to_study/<bookmark_count>", methods=["GET"])
@cross_domain
@requires_session
def new_bookmarks_to_study(bookmark_count):
    """
    Finds <bookmark_count> bookmarks that
    are recommended for this user to study and are not in the pipeline
    """
    int_count = int(bookmark_count)
    user = User.find_by_id(flask.g.user_id)
    new_to_study = user.get_new_bookmarks_to_study(int_count)
    json_bookmarks = [bookmark.as_dictionary() for bookmark in new_to_study]
    return json_result(json_bookmarks)


@api.route("/scheduled_bookmarks_count", methods=["GET"])
@cross_domain
@requires_session
def scheduled_bookmarks_count():
    """
    Returns a number of bookmarks that are in active learning.
    (Means the user has done at least on exercise in the past)
    """
    user = User.find_by_id(flask.g.user_id)
    bookmark_count = BasicSRSchedule.scheduled_bookmarks_count(user)

    return json_result(bookmark_count)


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
