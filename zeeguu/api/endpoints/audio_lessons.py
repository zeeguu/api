import flask

from zeeguu.api.utils.background import run_in_background
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator
from zeeguu.core.audio_lessons.script_generator import VALID_SUGGESTION_TYPES
from zeeguu.core.audio_lessons.suggestion_validator import validate_suggestion
from zeeguu.core.model import db, User, UserWord, AudioLessonGenerationProgress
from zeeguu.logging import log
from . import api


def _generate_lesson_in_background(user_id, preparation):
    """
    Run lesson generation in a background thread (called via run_in_background).

    The `preparation` dict contains everything needed to generate the lesson,
    passed as IDs rather than ORM objects since this runs in a separate DB session.
    Example:
        {
            "selected_word_ids": [42, 73, 91],
            "unscheduled_word_ids": [91],
            "origin_language": "nl",
            "translation_language": "en",
            "cefr_level": "B1",
            "progress_id": 5,
        }
    """
    progress = None
    try:
        # Re-fetch ORM objects by ID since we're in a new DB session
        user = User.find_by_id(user_id)
        progress = AudioLessonGenerationProgress.query.get(preparation["progress_id"])

        # Either could be None if deleted between request and background execution
        # (e.g., user deleted their account, or DB was cleaned up)
        if not user or not progress:
            log(f"[background_generate] User or progress record not found for user {user_id}")
            return

        selected_words = UserWord.query.filter(
            UserWord.id.in_(preparation["selected_word_ids"])
        ).all()
        # .in_() doesn't preserve order, so re-sort to match the original selection
        word_order = {wid: i for i, wid in enumerate(preparation["selected_word_ids"])}
        selected_words.sort(key=lambda w: word_order.get(w.id, 0))

        unscheduled_words = UserWord.query.filter(
            UserWord.id.in_(preparation["unscheduled_word_ids"])
        ).all() if preparation["unscheduled_word_ids"] else []

        generator = DailyLessonGenerator()
        generator.generate_daily_lesson(
            user=user,
            selected_words=selected_words,
            unscheduled_words=unscheduled_words,
            origin_language=preparation["origin_language"],
            translation_language=preparation["translation_language"],
            cefr_level=preparation["cefr_level"],
            progress=progress,
            suggestion=preparation.get("suggestion"),
            suggestion_type=preparation.get("suggestion_type"),
            is_general=preparation.get("is_general", False),
        )
    except Exception as e:
        log(f"[background_generate] Error for user {user_id}: {e}")
        try:
            if not progress:
                progress = AudioLessonGenerationProgress.query.get(preparation["progress_id"])
            if progress:
                progress.mark_error(str(e))
                db.session.commit()
        except Exception:
            pass


@api.route("/generate_daily_lesson", methods=["POST"])
@cross_domain
@requires_session
def generate_daily_lesson():
    """
    Generate a daily audio lesson for the current user.
    Validates synchronously, then starts generation in a background thread.
    Returns 202 immediately; use the progress endpoint to track generation.

    Form data:
    - timezone_offset (optional): Client's timezone offset in minutes from UTC
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()

    # Get timezone offset from form data (default to 0 for UTC)
    timezone_offset = flask.request.form.get("timezone_offset", 0, type=int)
    suggestion = flask.request.form.get("suggestion", "").strip()[:80].strip() or None
    suggestion_type = flask.request.form.get("suggestion_type", "").strip() or None
    if suggestion_type not in (None, *VALID_SUGGESTION_TYPES):
        suggestion_type = None

    # Validate and canonicalize the suggestion
    canonical_suggestion = None
    is_general_topic = False
    if suggestion and suggestion_type:
        is_valid, validation_result = validate_suggestion(suggestion, suggestion_type, user.native_language.name)
        if not is_valid:
            return json_result({"error": f"Can't generate a lesson for this: {validation_result['reason']}"}), 400
        canonical_suggestion = validation_result["canonical"]
        is_general_topic = validation_result["is_general"]

    result = generator.prepare_lesson_generation(user, timezone_offset, canonical_suggestion, suggestion_type)

    # Existing lesson found — return it directly
    if result.get("lesson_id"):
        return json_result(result), 200

    # Validation error — return it
    if result.get("error"):
        status_code = result.pop("status_code", 400)
        return json_result(result), status_code

    # Validation passed (has selected_word_ids) — kick off generation in background
    if "selected_word_ids" not in result:
        return json_result({"error": "Unexpected preparation result"}), 500

    result["is_general"] = is_general_topic
    run_in_background(_generate_lesson_in_background, user.id, result)

    return json_result({"status": "generating", "message": "Lesson generation started"}), 202


@api.route("/get_daily_lesson", methods=["GET"])
@cross_domain
@requires_session
def get_daily_lesson():
    """
    Get an existing daily audio lesson for the current user.
    Returns the most recent lesson or a specific lesson by ID.

    Query parameters:
    - lesson_id (optional): specific lesson ID to retrieve
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()
    lesson_id = flask.request.args.get("lesson_id")

    result = generator.get_daily_lesson_for_user(user, lesson_id)

    # Check if there's a specific status code to return
    status_code = result.pop("status_code", 200)

    return json_result(result), status_code


@api.route("/get_todays_lesson", methods=["GET"])
@cross_domain
@requires_session
def get_todays_lesson():
    """
    Get today's daily audio lesson for the current user.
    Returns the lesson created today if it exists.

    Query parameters:
    - timezone_offset (optional): Client's timezone offset in minutes from UTC
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()

    # Get timezone offset from query parameter (default to 0 for UTC)
    timezone_offset = flask.request.args.get("timezone_offset", 0, type=int)

    result = generator.get_todays_lesson_for_user(user, timezone_offset)

    # Check if there's a specific status code to return
    status_code = result.pop("status_code", 200)

    return json_result(result), status_code


@api.route("/delete_todays_lesson", methods=["DELETE"])
@cross_domain
@requires_session
def delete_todays_lesson():
    """
    Delete today's daily audio lesson for the current user.
    Removes both the database record and the audio file.

    Query parameters:
    - timezone_offset (optional): Client's timezone offset in minutes from UTC
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()

    # Get timezone offset from query parameter (default to 0 for UTC)
    timezone_offset = flask.request.args.get("timezone_offset", 0, type=int)

    result = generator.delete_todays_lesson_for_user(user, timezone_offset)

    # Check if there's a specific status code to return
    status_code = result.pop("status_code", 200)

    return json_result(result), status_code


@api.route("/past_daily_lessons", methods=["GET"])
@cross_domain
@requires_session
def get_past_daily_lessons():
    """
    Get past daily audio lessons for the current user with pagination.

    Query parameters:
    - limit (optional): Maximum number of lessons to return (default 20, max 100)
    - offset (optional): Number of lessons to skip for pagination (default 0)
    - timezone_offset (optional): Client's timezone offset in minutes from UTC
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()

    # Get pagination parameters
    try:
        limit = min(int(flask.request.args.get("limit", 20)), 100)  # Max 100
        offset = int(flask.request.args.get("offset", 0))
        timezone_offset = int(flask.request.args.get("timezone_offset", 0))
    except ValueError:
        return json_result({"error": "Invalid parameters"}), 400

    result = generator.get_past_daily_lessons_for_user(
        user, limit, offset, timezone_offset
    )

    # Check if there's a specific status code to return
    status_code = result.pop("status_code", 200)

    return json_result(result), status_code


@api.route("/check_daily_lesson_feasibility", methods=["GET"])
@cross_domain
@requires_session
def check_daily_lesson_feasibility():
    """
    Check if it's feasible to generate a daily audio lesson for the current user.
    This checks prerequisites without actually generating a lesson.

    Returns:
    {
        "feasible": true/false,
        "available_words": 5,
        "required_words": 2,
        "learned_language": "de",
        "message": "Ready to generate lesson" | "Not enough words available"
    }
    """
    user = User.find_by_id(flask.g.user_id)

    # Import the word selector to check available words
    from zeeguu.core.audio_lessons.word_selector import select_words_for_audio_lesson
    
    # Check how many words are available for lesson generation
    selected_words, _ = select_words_for_audio_lesson(
        user, 3, return_unscheduled_info=True
    )
    
    available_words = len(selected_words)
    required_words = 2
    feasible = available_words >= required_words
    
    if feasible:
        message = f"Ready to generate lesson with {available_words} words available"
    else:
        message = f"Not enough words available. Need at least {required_words} words, but only {available_words} available"
    
    return json_result({
        "feasible": feasible,
        "available_words": available_words,
        "required_words": required_words,
        "learned_language": user.learned_language.code if user.learned_language else None,
        "message": message
    })


@api.route("/update_lesson_state/<int:lesson_id>", methods=["POST"])
@cross_domain
@requires_session
def update_lesson_state(lesson_id):
    """
    Update the state of a daily audio lesson.

    JSON payload:
    {
        "action": "play|pause|resume|complete",
        "position_seconds": 123  // required for pause action
    }
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()

    # Get JSON data from request
    try:
        state_data = flask.request.get_json()
        if not state_data or "action" not in state_data:
            return (
                json_result(
                    {"error": "Missing required 'action' field in JSON payload"}
                ),
                400,
            )
    except Exception:
        return json_result({"error": "Invalid JSON payload"}), 400

    result = generator.update_lesson_state_for_user(user, lesson_id, state_data)

    # Check if there's a specific status code to return
    status_code = result.pop("status_code", 200)

    return json_result(result), status_code


@api.route("/audio_lesson_generation_progress", methods=["GET"])
@cross_domain
@requires_session
def get_audio_lesson_generation_progress():
    """
    Get the current progress of audio lesson generation for the current user.
    Used for displaying real-time progress in the UI during lesson generation.

    Returns:
    {
        "status": "pending|generating_script|synthesizing_audio|combining_audio|done|error",
        "current_step": 5,
        "total_steps": 20,
        "current_word": 2,
        "total_words": 3,
        "message": "Word 2/3: Synthesizing teacher (5/20)",
        "started_at": "2024-01-15T10:30:00"
    }

    Returns null if no generation is in progress.
    """
    user = User.find_by_id(flask.g.user_id)

    progress = AudioLessonGenerationProgress.find_active_for_user(user)

    if not progress:
        return json_result({"progress": None})

    # Detect stuck generations (e.g., server restarted mid-generation)
    from datetime import datetime, timedelta
    if progress.updated_at and datetime.utcnow() - progress.updated_at > timedelta(minutes=2):
        progress.mark_error("Generation appears to have stopped. Please try again.")
        db.session.commit()

    return json_result({"progress": progress.to_dict()})
