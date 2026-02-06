import flask

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator
from zeeguu.core.model import User, AudioLessonGenerationProgress
from . import api


@api.route("/generate_daily_lesson", methods=["POST"])
@cross_domain
@requires_session
def generate_daily_lesson():
    """
    Generate a daily audio lesson for the current user.
    Selects 3 most important words that are currently being learned
    and haven't been in previous lessons.

    Form data:
    - timezone_offset (optional): Client's timezone offset in minutes from UTC
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()

    # Get timezone offset from form data (default to 0 for UTC)
    timezone_offset = flask.request.form.get("timezone_offset", 0, type=int)

    result = generator.generate_daily_lesson_for_user(user, timezone_offset)

    # Check if there's a specific status code to return
    status_code = result.pop("status_code", 200 if "error" not in result else 400)

    return json_result(result), status_code


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
        "has_feature_access": true,
        "learned_language": "de",
        "message": "Ready to generate lesson" | "Not enough words available" | "Feature not available"
    }
    """
    user = User.find_by_id(flask.g.user_id)
    
    # Check if user has access to daily audio lessons
    has_feature_access = user.has_feature("daily_audio")
    if not has_feature_access:
        return json_result({
            "feasible": False,
            "available_words": 0,
            "required_words": 2,
            "has_feature_access": False,
            "learned_language": user.learned_language.code if user.learned_language else None,
            "message": "Daily audio lessons feature not available for this user"
        })

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
        "has_feature_access": has_feature_access,
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

    progress = AudioLessonGenerationProgress.find_for_user(user)

    if not progress:
        return json_result({"progress": None})

    return json_result({"progress": progress.to_dict()})
