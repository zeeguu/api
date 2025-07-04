import flask

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator
from zeeguu.core.model import User
from . import api


@api.route("/generate_daily_lesson", methods=["POST"])
@cross_domain
@requires_session
def generate_daily_lesson():
    """
    Generate a daily audio lesson for the current user.
    Selects 3 most important words that are currently being learned
    and haven't been in previous lessons.
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()
    
    result = generator.generate_daily_lesson_for_user(user)
    
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
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()
    
    result = generator.get_todays_lesson_for_user(user)
    
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
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()
    
    result = generator.delete_todays_lesson_for_user(user)
    
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
    """
    user = User.find_by_id(flask.g.user_id)
    generator = DailyLessonGenerator()
    
    # Get pagination parameters
    try:
        limit = min(int(flask.request.args.get("limit", 20)), 100)  # Max 100
        offset = int(flask.request.args.get("offset", 0))
    except ValueError:
        return json_result({"error": "Invalid pagination parameters"}), 400
    
    result = generator.get_past_daily_lessons_for_user(user, limit, offset)
    
    # Check if there's a specific status code to return
    status_code = result.pop("status_code", 200)
    
    return json_result(result), status_code


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
            return json_result({"error": "Missing required 'action' field in JSON payload"}), 400
    except Exception:
        return json_result({"error": "Invalid JSON payload"}), 400
    
    result = generator.update_lesson_state_for_user(user, lesson_id, state_data)
    
    # Check if there's a specific status code to return
    status_code = result.pop("status_code", 200)
    
    return json_result(result), status_code
