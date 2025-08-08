import traceback
import flask
from sqlalchemy.exc import NoResultFound

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
    user_words = BasicSRSchedule.scheduled_user_words(user)

    return _user_words_as_json_result(user_words)


@api.route("/count_of_all_scheduled_words", methods=["GET"])
@cross_domain
@requires_session
def get_count_of_all_scheduled_words():
    user = User.find_by_id(flask.g.user_id)
    word_count = BasicSRSchedule.scheduled_user_words_count(user)
    return json_result(word_count)


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
    to_study = BasicSRSchedule.user_words_to_study(user)
    return _user_words_as_json_result(to_study)


@api.route("/count_of_bookmarks_recommended_for_practice", methods=["GET"])
@cross_domain
@requires_session
def get_count_of_bookmarks_recommended_for_practice():

    user = User.find_by_id(flask.g.user_id)
    to_study = BasicSRSchedule.user_words_to_study(user)
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
    to_study = BasicSRSchedule.scheduled_words_due_today(user)

    return _user_words_as_json_result(to_study, True, with_tokens)


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
    next_in_learning = BasicSRSchedule.user_words_not_scheduled(user, 6)

    return _user_words_as_json_result(next_in_learning)


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
        bookmark.user_word.report_exercise_outcome(
            db_session,
            source,
            outcome,
            solving_speed,
            session_id,
            other_feedback,
        )

        return "OK"
    except NoResultFound:
        print(f"Bookmark {bookmark_id} not found")
        return "FAIL - Bookmark not found"
    except Exception as e:
        traceback.print_exc()
        print(f"Error reporting exercise outcome: {e}")
        return "FAIL"


@api.route("/similar_words/<bookmark_id>", methods=["GET"])
@cross_domain
@requires_session
def similar_words_api(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    user = User.find_by_id(flask.g.user_id)
    return json_result(
        similar_words(
            bookmark.user_word.meaning.origin.content,
            bookmark.user_word.meaning.origin.language,
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


def _user_words_as_json_result(user_words):
    from zeeguu.logging import log
    from zeeguu.core.model import db
    
    dicts = []
    words_to_delete = []
    
    for user_word in user_words:
        try:
            # The as_dictionary() method already calls validate_data_integrity()
            # which will auto-repair if possible or raise ValueError if not
            dicts.append(user_word.as_dictionary())
        except ValueError as e:
            # This means validate_data_integrity() couldn't repair the issue
            # (i.e., UserWord has no bookmarks at all)
            log(f"UserWord {user_word.id} failed validation and cannot be repaired: {str(e)}")
            words_to_delete.append(user_word)
        except Exception as e:
            # Log any other unexpected errors and skip
            log(f"Unexpected error processing UserWord {user_word.id}: {str(e)}")
            continue
    
    # Delete UserWords that couldn't be repaired
    if words_to_delete:
        for word in words_to_delete:
            try:
                db.session.delete(word)
                log(f"Deleted UserWord {word.id} due to unrepairable data integrity issues")
            except:
                log(f"Failed to delete UserWord {word.id}")
        try:
            db.session.commit()
        except:
            db.session.rollback()
            log("Failed to commit UserWord deletions")
    
    return json_result(dicts)
