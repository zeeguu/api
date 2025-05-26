import traceback
import flask

from zeeguu.core.exercises.similar_words import similar_words
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.user import User

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.parse_json_boolean import parse_json_boolean
from . import api, db_session
from flask import request

from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule


# ====================================
#  All Scheduled Bookmarks
# ====================================
@api.route("/all_scheduled_bookmarks", methods=["GET", "POST"])
@cross_domain
@requires_session
def get_all_scheduled_bookmarks():
    """
    Returns all the words scheduled for learning
    Is used to render the Words>Learning page
    """
    user = User.find_by_id(flask.g.user_id)
    user_meanings = BasicSRSchedule.scheduled_meanings(user)

    return _user_meanings_as_json_result(user_meanings)


@api.route("/count_of_all_scheduled_bookmarks", methods=["GET"])
@cross_domain
@requires_session
def get_count_of_all_scheduled_bookmarks():
    user = User.find_by_id(flask.g.user_id)
    bookmark_count = BasicSRSchedule.scheduled_meanings_count(user)
    return json_result(bookmark_count)


# ====================================
# Bookmarks recommended for practice
# ====================================
@api.route(
    "/bookmarks_recommended_for_practice",
    methods=["GET"],
)
@cross_domain
@requires_session
def get_bookmarks_recommended_for_practice():

    user = User.find_by_id(flask.g.user_id)
    to_study = BasicSRSchedule.user_meanings_to_study(user)
    return _user_meanings_as_json_result(to_study)


@api.route("/count_of_bookmarks_recommended_for_practice", methods=["GET"])
@cross_domain
@requires_session
def get_count_of_bookmarks_recommended_for_practice():

    user = User.find_by_id(flask.g.user_id)
    to_study = BasicSRSchedule.user_meanings_to_study(user)
    return json_result(len(to_study))


@api.route(
    "/bookmarks_due_today",
    methods=["GET"],
)
@cross_domain
@requires_session
def get_bookmarks_due_today():

    user = User.find_by_id(flask.g.user_id)
    with_tokens = parse_json_boolean(request.form.get("with_context", "false"))
    to_study = BasicSRSchedule.scheduled_meanings_due_today(user)

    return _user_meanings_as_json_result(to_study, True, with_tokens)


# =====================================
# Bookmarks next to be studied
# =====================================


@api.route(
    "/bookmarks_next_in_learning",
    methods=["GET"],
)
@cross_domain
@requires_session
def get_bookmarks_next_in_learning():

    user = User.find_by_id(flask.g.user_id)
    next_in_learning = BasicSRSchedule.user_meanings_not_scheduled(user, 6)

    return _user_meanings_as_json_result(next_in_learning)


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
        print(db_session)
        bookmark.user_meaning.report_exercise_outcome(
            db_session,
            source,
            outcome,
            solving_speed,
            session_id,
            other_feedback,
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
        similar_words(
            bookmark.user_meaning.meaning.origin.content,
            bookmark.user_meaning.meaning.origin.language,
            user,
        )
    )


def _bookmarks_as_json_result(bookmarks, with_exercise_info, with_tokens):
    bookmark_dicts = [
        b.as_dictionary(
            with_exercise_info=with_exercise_info, with_context_tokenized=with_tokens
        )
        for b in bookmarks
    ]
    return json_result(bookmark_dicts)


def _user_meanings_as_json_result(user_meanings):
    dicts = [um.as_dictionary() for um in user_meanings]
    return json_result(dicts)
