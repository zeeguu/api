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
    result = serialize_streak_values(user_language, is_detailed=True)
    return json_result(result)


@api.route("/all_language_streaks", methods=["GET"])
@cross_domain
@requires_session
def get_all_language_streaks():
    user = User.find_by_id(flask.g.user_id)
    user_languages = UserLanguage.query.filter_by(user_id=user.id).all()
    user_languages = [ul for ul in user_languages if ul.language_id != user.native_language_id]
    # Sort by daily streak descending before serializing
    user_languages.sort(key=lambda ul: ul.daily_streak, reverse=True)
    result = [
        serialize_language_and_streak_values(ul, include_streak_data=True, is_detailed=False)
        for ul in user_languages
    ]
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
    # Sort by max streak descending before serializing
    user_languages.sort(key=lambda ul: ul.max_streak, reverse=True)
    result = [
        serialize_language_and_streak_values(ul, include_streak_data=self_or_friend, is_detailed=True)
        for ul in user_languages
    ]
    return json_result(result)


def serialize_language_and_streak_values(user_language: UserLanguage, include_streak_data: bool = False,
                                         is_detailed: bool = False) -> dict:
    result = {
        "code": user_language.language.code,
        "language": user_language.language.name,
    }
    if include_streak_data:
        result.update(serialize_streak_values(user_language, is_detailed))
    return result


def serialize_streak_values(user_language: UserLanguage, is_detailed: bool = False) -> dict:
    result = {"daily_streak": user_language.daily_streak}
    if is_detailed:
        result.update({
            "max_streak": user_language.max_streak,
            "max_streak_date": user_language.max_streak_date.strftime(
                "%Y-%m-%d") if user_language.max_streak_date else None
        })
    return result
