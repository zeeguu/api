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

    result = generator.generate_daily_lesson(user)

    if "error" in result:
        return json_result(result), 400

    return json_result(result)
