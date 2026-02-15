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
#  All Scheduled User Words
# ====================================
@api.route("/all_scheduled_user_words", methods=["GET", "POST"])
@cross_domain
@requires_session
def get_all_scheduled_user_words():
    """
    Returns all the user words scheduled for learning
    Is used to render the Words>Learning page
    """
    user = User.find_by_id(flask.g.user_id)
    user_words = BasicSRSchedule.scheduled_user_words(user)

    return _user_words_as_json_result(user_words)


@api.route("/count_of_all_scheduled_user_words", methods=["GET"])
@cross_domain
@requires_session
def get_count_of_all_scheduled_user_words():
    user = User.find_by_id(flask.g.user_id)
    word_count = BasicSRSchedule.scheduled_user_words_count(user)
    return json_result(word_count)


# ====================================
# User words recommended for practice
# ====================================
@api.route(
    "/user_words_recommended_for_practice",
    methods=["GET"],
)
@cross_domain
@requires_session
def get_user_words_recommended_for_practice():

    user = User.find_by_id(flask.g.user_id)
    to_study = BasicSRSchedule.user_words_to_study(user)
    return _user_words_as_json_result(to_study)


@api.route("/count_of_user_words_recommended_for_practice", methods=["GET"])
@cross_domain
@requires_session
def get_count_of_user_words_recommended_for_practice():
    """
    Returns the count of user words recommended for practice.
    Uses the same validation logic as user_words_recommended_for_practice
    to ensure the count matches the actual exercises shown.
    """
    user = User.find_by_id(flask.g.user_id)
    to_study = BasicSRSchedule.user_words_to_study(user)
    # Count only valid user words (same filtering as the actual exercises endpoint)
    valid_count = _count_valid_user_words(to_study)
    return json_result(valid_count)


@api.route("/next_word_due_time", methods=["GET"])
@cross_domain
@requires_session
def get_next_word_due_time():
    """
    Returns when the next word is due for practice.
    Used by frontend to show "Next word available in X minutes" messages.

    Returns:
        - null if no words are scheduled
        - ISO timestamp string if a word is scheduled
    """
    user = User.find_by_id(flask.g.user_id)
    next_time = BasicSRSchedule.next_practice_time_for_user(user)

    if next_time is None:
        return json_result(None)

    return json_result(next_time.isoformat())


@api.route(
    "/user_words_due_today",
    methods=["GET"],
)
@cross_domain
@requires_session
def get_user_words_due_today():

    user = User.find_by_id(flask.g.user_id)
    with_tokens = parse_json_boolean(request.form.get("with_context", "false"))
    to_study = BasicSRSchedule.scheduled_words_due_today(user)

    return _user_words_as_json_result(to_study, True, with_tokens)


# =====================================
# User words next to be studied
# =====================================


@api.route(
    "/user_words_next_in_learning",
    methods=["GET"],
)
@cross_domain
@requires_session
def get_user_words_next_in_learning():

    user = User.find_by_id(flask.g.user_id)
    next_in_learning = BasicSRSchedule.user_words_not_scheduled(user, 6)

    return _user_words_as_json_result(next_in_learning)


# ====================================
# Backward compatibility (deprecated)
# ====================================
@api.route("/all_scheduled_bookmarks", methods=["GET", "POST"])
@cross_domain
@requires_session
def get_all_scheduled_bookmarks():
    """DEPRECATED: Use /all_scheduled_user_words instead"""
    return get_all_scheduled_user_words()

@api.route("/count_of_all_scheduled_words", methods=["GET"])
@cross_domain
@requires_session
def get_count_of_all_scheduled_words():
    """DEPRECATED: Use /count_of_all_scheduled_user_words instead"""
    return get_count_of_all_scheduled_user_words()

@api.route("/bookmarks_recommended_for_practice", methods=["GET"])
@cross_domain
@requires_session
def get_bookmarks_recommended_for_practice():
    """DEPRECATED: Use /user_words_recommended_for_practice instead"""
    return get_user_words_recommended_for_practice()

@api.route("/count_of_bookmarks_recommended_for_practice", methods=["GET"])
@cross_domain
@requires_session
def get_count_of_bookmarks_recommended_for_practice():
    """DEPRECATED: Use /count_of_user_words_recommended_for_practice instead"""
    return get_count_of_user_words_recommended_for_practice()

@api.route("/bookmarks_due_today", methods=["GET"])
@cross_domain
@requires_session
def get_bookmarks_due_today():
    """DEPRECATED: Use /user_words_due_today instead"""
    return get_user_words_due_today()

@api.route("/bookmarks_next_in_learning", methods=["GET"])
@cross_domain
@requires_session
def get_bookmarks_next_in_learning():
    """DEPRECATED: Use /user_words_next_in_learning instead"""
    return get_user_words_next_in_learning()


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

    :param exercise_outcome: One of: C, Retry, Wrong, Typo, Too easy...
    :param exercise_source: has been assigned to your app by zeeguu
    :param exercise_solving_speed: in milliseconds
    :param user_word_id: the user_word for which the data is reported
    :param session_id: assuming that the exercise submitter knows which session is this exercise part of
    :return:
    """

    outcome = request.form.get("outcome", "")
    source = request.form.get("source")
    solving_speed = request.form.get("solving_speed")
    user_word_id = request.form.get("user_word_id")
    other_feedback = request.form.get("other_feedback")
    session_id = int(request.form.get("session_id"))

    if not solving_speed.isdigit():
        solving_speed = 0

    try:
        from zeeguu.core.model.user_word import UserWord
        user_word = UserWord.query.get(user_word_id)
        if not user_word:
            return "FAIL - UserWord not found"
            
        user_word.report_exercise_outcome(
            db_session,
            source,
            outcome,
            solving_speed,
            session_id,
            other_feedback,
        )

        return "OK"
    except Exception as e:
        traceback.print_exc()
        print(f"Error reporting exercise outcome for UserWord {user_word_id}: {e}")
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


def _count_valid_user_words(user_words):
    """
    Count user words that pass validation.
    Uses the same validation logic as _user_words_as_json_result to ensure
    the badge count matches the actual exercises shown.
    """
    if not user_words:
        return 0

    valid_count = 0
    for user_word in user_words:
        try:
            # Validate that the user_word can be serialized (same check as _user_words_as_json_result)
            user_word.as_dictionary()
            valid_count += 1
        except (ValueError, Exception):
            # Skip invalid user words (same as _user_words_as_json_result)
            continue

    return valid_count


def _user_words_as_json_result(user_words):
    from zeeguu.logging import log
    from zeeguu.core.model import db
    from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord

    if not user_words:
        return json_result([])

    # Batch-load all schedules in ONE query to avoid N+1 problem
    # Use FourLevelsPerWord (the actual subclass) to get proper polymorphic behavior
    user_word_ids = [uw.id for uw in user_words]
    schedules = FourLevelsPerWord.query.filter(
        FourLevelsPerWord.user_word_id.in_(user_word_ids)
    ).all()

    # Create a lookup map: user_word_id -> schedule
    schedule_map = {s.user_word_id: s for s in schedules}

    # Get tokenized contexts - use cache when available
    context_map = {}  # user_word_id -> tokenized_context

    for uw in user_words:
        try:
            bm = uw.preferred_bookmark
            if bm and bm.context:
                # Use cached tokenization if available, otherwise tokenize and cache
                tokenized = bm.context.get_tokenized(session=db.session)
                if tokenized:
                    context_map[uw.id] = tokenized
        except Exception as e:
            log(f"Failed to get tokenized context for user_word {uw.id}: {e}")

    dicts = []
    words_to_delete = []

    for user_word in user_words:
        try:
            # Pass pre-loaded schedule and pre-tokenized context
            schedule = schedule_map.get(user_word.id)
            tokenized_context = context_map.get(user_word.id)
            dicts.append(user_word.as_dictionary(
                schedule=schedule,
                pre_tokenized_context=tokenized_context
            ))
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


# ====================================
# Report Exercise Issue
# ====================================


@api.route("/report_exercise_issue", methods=["POST"])
@cross_domain
@requires_session
def report_exercise_issue():
    """
    Report a problem with an exercise.

    Request body (JSON):
    {
        "bookmark_id": 123,
        "exercise_source": "FindWordInContextCloze",
        "reason": "word_not_shown",  // word_not_shown, context_confusing, wrong_translation, context_wrong, other
        "comment": "Optional details",  // optional
        "context_used": "The context sentence..."  // optional
    }

    Response (200):
    {
        "success": true,
        "message": "Report submitted",
        "report_id": 123
    }
    """
    from zeeguu.logging import log
    from zeeguu.core.model import ExerciseReport, ExerciseSource

    user = User.find_by_id(flask.g.user_id)
    data = request.get_json()

    if not data:
        return json_result({"error": "JSON body required"}), 400

    bookmark_id = data.get("bookmark_id")
    exercise_source_name = data.get("exercise_source", "").strip()
    reason = data.get("reason", "").strip()
    comment = (data.get("comment") or "").strip() or None
    context_used = (data.get("context_used") or "").strip() or None

    if not bookmark_id or not exercise_source_name or not reason:
        return json_result({"error": "bookmark_id, exercise_source, and reason are required"}), 400

    valid_reasons = ["word_not_shown", "wrong_highlighting", "context_confusing", "wrong_translation", "context_wrong", "other"]
    if reason not in valid_reasons:
        return json_result({"error": f"reason must be one of: {valid_reasons}"}), 400

    # Find the bookmark
    bookmark = Bookmark.find(bookmark_id)
    if not bookmark:
        return json_result({"error": "Bookmark not found"}), 404

    # Find or create the exercise source
    exercise_source = ExerciseSource.find_or_create(db_session, exercise_source_name)

    # Check if already reported
    existing = ExerciseReport.find_by_user_bookmark_source(
        user.id, bookmark.id, exercise_source.id
    )
    if existing:
        return json_result({
            "success": True,
            "message": "You have already reported this exercise",
            "report_id": existing.id,
            "already_reported": True
        })

    try:
        report = ExerciseReport.create(
            db_session, user, bookmark, exercise_source, reason, comment, context_used
        )
        log(f"User {user.id} reported exercise issue for bookmark {bookmark.id}: {reason}")

        return json_result({
            "success": True,
            "message": "Thanks for the feedback!",
            "report_id": report.id
        })
    except Exception as e:
        log(f"Error creating exercise report: {e}")
        traceback.print_exc()
        return json_result({"error": "Failed to submit report"}), 500
