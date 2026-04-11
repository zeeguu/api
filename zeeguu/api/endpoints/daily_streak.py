import flask

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.util.time import user_local_today
from . import api
from ...core.model import User
from ...core.model.user_language import UserLanguage
from ...core.model.db import db


@api.route("/daily_streak", methods=["GET"])
@cross_domain
@requires_session
def get_daily_streak():
    user = User.find_by_id(flask.g.user_id)
    ul = UserLanguage.find_or_create(db.session, user, user.learned_language)
    return json_result({"daily_streak": ul.current_daily_streak})


@api.route("/all_language_streaks", methods=["GET"])
@cross_domain
@requires_session
def get_all_language_streaks():
    user = User.find_by_id(flask.g.user_id)
    today = user_local_today(user)
    result = [
        {
            "code": ul.language.code,
            "language": ul.language.name,
            "daily_streak": ul.current_daily_streak,
            "practiced_today": ul.local_last_practiced == today,
        }
        for ul in UserLanguage.query.filter_by(user_id=user.id).all()
        if ul.language_id != user.native_language_id
    ]
    result.sort(key=lambda x: x["daily_streak"], reverse=True)
    return json_result(result)
