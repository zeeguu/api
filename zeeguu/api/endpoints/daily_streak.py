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
@api.route("/all_daily_streak/<username>", methods=["GET"])
@cross_domain
@requires_session
def get_all_daily_streak(username: str = None):
    requester_user_id = flask.g.user_id
    self_or_friend = True
    if username is not None:
        requested_user = User.find_by_username(username)
        if requested_user is None:
            return []
        requested_user_id = requested_user.id
        if requester_user_id != requested_user_id and not Friend.are_friends(requester_user_id, requested_user_id):
            self_or_friend = False
    else:
        requested_user_id = requester_user_id

    user = User.find_by_id(requested_user_id)
    user_languages = UserLanguage.all_user_languages_for_user(user)
    result = []
    for user_language in user_languages:
        obj = {
            "language": user_language.language.as_dictionary(),
        }
        if self_or_friend:
            obj.update({
                "daily_streak": user_language.daily_streak or 0,
                "max_streak": user_language.max_streak or 0,
                "max_streak_date": user_language.max_streak_date.strftime(
                    "%Y-%m-%d") if user_language.max_streak_date else None
            })
        result.append(obj)
    return json_result(result)
