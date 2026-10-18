import traceback
import flask
from sqlalchemy.exc import NoResultFound

from zeeguu.core.exercises.example_contexts import replace_fragments_before_first_exercise
from zeeguu.core.exercises.similar_words import similar_words
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.user import User

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.input_limits import abort_if_too_long, MAX_PHRASE_CHARS
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
    # Before a word's first exercise, a context the reader cut short gives
    # way to a generated example sentence (see example_contexts).
    replace_fragments_before_first_exercise(db_session, to_study)
    return _user_words_as_json_result(to_study)


@api.route("/count_of_user_words_recommended_for_practice", methods=["GET"])
@cross_domain
@requires_session
def get_count_of_user_words_recommended_for_practice():
    """
    Returns the count of user words recommended for practice.
    Counts what user_words_as_dicts returns, so the badge matches the
    exercises shown. Serializing word by word instead (no batch-loaded
    schedules, tokenizing on demand) took this endpoint up to 140s in
    Sep-Oct 2026 while the exercises endpoint itself stayed under 15s.
    """
    user = User.find_by_id(flask.g.user_id)
    to_study = BasicSRSchedule.user_words_to_study(user)
    return json_result(len(user_words_as_dicts(to_study)))


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
        # A word of another user is answered exactly like a missing one
        if not user_word or user_word.user_id != flask.g.user_id:
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
    bookmark = Bookmark.query.get(bookmark_id)
    if not bookmark or bookmark.user_word.user_id != flask.g.user_id:
        return json_result({"error": "Bookmark not found"}, status=404)
    user = User.find_by_id(flask.g.user_id)
    return json_result(
        similar_words(
            bookmark.user_word.meaning.origin.content,
            bookmark.user_word.meaning.origin.language,
            user,
        )
    )


@api.route("/judge_cloze_alternative", methods=["POST"])
@cross_domain
@requires_session
def judge_cloze_alternative():
    """
    Whether a word the learner typed into a cloze, other than the expected one,
    also fits the blank ("tænker" where the exercise expected "synes").

    JSON body: {"bookmark_id": int, "typed": str}
    Returns:   {"relation": "SYNONYM" | "NEAR_SYNONYM_NOT_IDIOMATIC"
                            | "NOT_SYNONYM" | "UNKNOWN",
                "explanation": str, "cached": bool}

    UNKNOWN: the judge could not be asked in time; the client treats the
    answer as wrong, as it did before this existed.
    """
    from zeeguu.core.exercises.cloze_alternatives import judge_alternative

    data = request.get_json(silent=True) or {}
    bookmark_id = data.get("bookmark_id")
    typed = data.get("typed")
    if not bookmark_id or not isinstance(typed, str):
        return json_result({"error": "bookmark_id and typed are required"}, status=400)
    # One word typed into a blank. Anything long is not an answer, and it
    # would go into the judge's prompt verbatim.
    abort_if_too_long("typed", typed, MAX_PHRASE_CHARS)

    bookmark = Bookmark.query.get(bookmark_id)
    if not bookmark or bookmark.user_word.user_id != flask.g.user_id:
        return json_result({"error": "Bookmark not found"}, status=404)

    return json_result(judge_alternative(db_session, bookmark, typed))


@api.route("/judge_translation_alternative", methods=["POST"])
@cross_domain
@requires_session
def judge_translation_alternative():
    """
    Whether a translation the learner typed for the bookmark's word, other
    than the stored one, is also right ("consult" where the exercise expected
    "look up" for "slå op").

    JSON body and reply as for /judge_cloze_alternative.
    """
    from zeeguu.core.exercises.cloze_alternatives import judge_translation_alternative

    data = request.get_json(silent=True) or {}
    bookmark_id = data.get("bookmark_id")
    typed = data.get("typed")
    if not bookmark_id or not isinstance(typed, str):
        return json_result({"error": "bookmark_id and typed are required"}, status=400)

    bookmark = Bookmark.query.get(bookmark_id)
    if not bookmark or bookmark.user_word.user_id != flask.g.user_id:
        return json_result({"error": "Bookmark not found"}, status=404)

    return json_result(judge_translation_alternative(db_session, bookmark, typed))


def _bookmarks_as_json_result(bookmarks, with_exercise_info, with_tokens):
    bookmark_dicts = [
        b.as_dictionary(
            with_exercise_info=with_exercise_info, with_context_tokenized=with_tokens
        )
        for b in bookmarks
    ]
    # Drop bookmarks whose `from` couldn't be located in their context
    # (#618 discontiguous-idiom family) — the anchor would be unreliable.
    bookmark_dicts = [b for b in bookmark_dicts if not b.get("_unanchorable")]
    return json_result(bookmark_dicts)


def _user_words_as_json_result(user_words):
    return json_result(user_words_as_dicts(user_words))


def user_words_as_dicts(user_words, tokenize=True):
    """The Words pages' JSON for these user words. Repairs what it can on the
    way (see below), as it does whenever a learner opens the page.

    tokenize=False leaves out the tokenized context, which only exercises
    need: a miss costs a call to the stanza service (seconds under load), and
    a teacher's list of a student's 500 waiting words must not make 500."""
    from zeeguu.logging import log
    from zeeguu.core.model import db
    from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord

    if not user_words:
        return []

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

    for uw in user_words if tokenize else []:
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
                pre_tokenized_context=tokenized_context,
                with_context_tokenized=tokenize,
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

    # Drop entries whose preferred_bookmark anchor can't be located in
    # context_tokenized — exercises can't run without a reliable highlight.
    # (#618 discontiguous-idiom family; as_dictionary also marks the
    # user_word not_fit_for_study so it self-heals on next read.)
    dicts = [d for d in dicts if not d.get("_unanchorable")]

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

    return dicts


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
        "reason": "word_not_shown",  // word_not_shown, wrong_highlighting, context_confusing, wrong_translation, context_wrong, audio_broken, other
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

    valid_reasons = ["word_not_shown", "wrong_highlighting", "context_confusing", "wrong_translation", "context_wrong", "audio_broken", "other"]
    if reason not in valid_reasons:
        return json_result({"error": f"reason must be one of: {valid_reasons}"}), 400

    # Find the bookmark; one of another user counts as not found
    bookmark = Bookmark.query.get(bookmark_id)
    if not bookmark or bookmark.user_word.user_id != user.id:
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
