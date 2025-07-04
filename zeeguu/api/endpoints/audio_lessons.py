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
