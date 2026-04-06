import datetime

import flask

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model.friend import Friend
from . import api
from ...core.model import User
from ...core.model.db import db
from ...core.model.user_language import UserLanguage


@api.route("/daily_streak", methods=["GET"])
@cross_domain
@requires_session
def get_daily_streak():
    user = User.find_by_id(flask.g.user_id)
    user_language = UserLanguage.find_or_create(db.session, user, user.learned_language)
    streak = user_language.daily_streak or 0
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    if user_language.last_practiced and user_language.last_practiced.date() < yesterday:
        streak = 0
    return json_result({"daily_streak": streak})


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
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        practiced_today = (
                ul.last_practiced is not None
                and ul.last_practiced.date() == today
        )
        # Streak is only valid if practiced today or yesterday
        streak = ul.daily_streak or 0
        if ul.last_practiced and ul.last_practiced.date() < yesterday:
            streak = 0
        result.append({
            "code": ul.language.code,
            "language": ul.language.name,
            "daily_streak": streak,
            "practiced_today": practiced_today,
        })
    # Sort by streak descending so highest streaks come first
    result.sort(key=lambda x: x["daily_streak"], reverse=True)
    return json_result(result)


@api.route("/all_language_streaks_detailed", methods=["GET"])
@api.route("/all_language_streaks_detailed/<username>", methods=["GET"])
@cross_domain
@requires_session
def get_all_language_streaks_detailed(username: str = None):
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

    user_languages = UserLanguage.query.filter_by(user_id=requested_user_id).all()
    user_languages.sort(key=lambda ul: ul.max_streak, reverse=True)
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
