import flask

from zeeguu.core.model.friend import Friend
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
    return json_result({
        "daily_streak": user_language.daily_streak or 0,
        "max_streak": user_language.max_streak or 0,
        "max_streak_date": user_language.max_streak_date.strftime("%Y-%m-%d") if user_language.max_streak_date else None,
    })


@api.route("/all_daily_streak", methods=["GET"])
@api.route("/all_daily_streak/<int:user_id>", methods=["GET"])
@cross_domain
@requires_session
def get_all_daily_streak(user_id: int = None):
    requester_user_id = flask.g.user_id
    requested_user_id = user_id if user_id is not None else requester_user_id

    user = User.find_by_id(requested_user_id)
    user_languages = UserLanguage.all_user_languages_for_user(user)
    result = []
    for user_language in user_languages:
        obj = {
            "language": user_language.language.as_dictionary(),
        }
        if requester_user_id == requested_user_id or Friend.are_friends(requester_user_id, requested_user_id):
            obj.update({
                "daily_streak": user_language.daily_streak or 0,
                "max_streak": user_language.max_streak or 0,
                "max_streak_date": user_language.max_streak_date.strftime(
                    "%Y-%m-%d") if user_language.max_streak_date else None
            })
        result.append(obj)
    return json_result(result)


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
        result.append({
            "code": ul.language.code,
            "language": ul.language.name,
            "daily_streak": ul.daily_streak or 0,
        })
    # Sort by streak descending so highest streaks come first
    result.sort(key=lambda x: x["daily_streak"], reverse=True)
    return json_result(result)
