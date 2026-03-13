import flask

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api
from ...core.model import User
from ...core.model.user_language import UserLanguage
from ...core.model.db import db


@api.route("/daily_streak", methods=["GET"])
@cross_domain
@requires_session
def get_daily_streak():
    user = User.find_by_id(flask.g.user_id)
    user_language = UserLanguage.find_or_create(db.session, user, user.learned_language)
    return json_result({"daily_streak": user_language.daily_streak or 0})
