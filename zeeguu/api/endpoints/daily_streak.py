import datetime
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


@api.route("/all_language_streaks", methods=["GET"])
@cross_domain
@requires_session
def get_all_language_streaks():
    user = User.find_by_id(flask.g.user_id)
    user_languages = UserLanguage.query.filter_by(user_id=user.id).all()
    result = []
    for ul in user_languages:
        if ul.language_id == user.native_language_id:
            continue
        practiced_today = (
            ul.last_practiced is not None
            and ul.last_practiced.date() == datetime.date.today()
        )
        result.append({
            "code": ul.language.code,
            "language": ul.language.name,
            "daily_streak": ul.daily_streak or 0,
            "practiced_today": practiced_today,
        })
    # Sort by streak descending so highest streaks come first
    result.sort(key=lambda x: x["daily_streak"], reverse=True)
    return json_result(result)
