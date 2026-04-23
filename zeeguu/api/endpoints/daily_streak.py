import flask

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.util.time import user_local_today
from zeeguu.core.model.friendship import Friendship
from . import api
from ...core.model import User
from ...core.model.db import db
from ...core.model.user_language import UserLanguage


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


@api.route("/language_streak_history", methods=["GET"])
@cross_domain
@requires_session
def get_my_language_streak_history():
    """
           Retrieve detailed language streak information for the logged-in user.

           Returns:
               list[dict]: A list of dictionaries, each containing:
                   - code (str): The code of the language.
                   - language (str): The name of the language.
                   - daily_streak (int, optional): Current daily streak for the language.
                   - max_streak (int, optional): Max streak for the language.
                   - max_streak_date (str, optional): Date when the max streak was achieved at.
        """
    return json_result(_serialize_language_streaks(flask.g.user_id, include_private=True))


@api.route("/friend_language_streak_history/<username>", methods=["GET"])
@cross_domain
@requires_session
def get_friend_language_streak_history(username):
    """
           Retrieve detailed language streak information for a user.

           Returns the given user's language streaks only if they are friends with the requester.
           Otherwise, returns the requester's own language streaks.

           Args:
               username (str): The username of the user whose streaks are requested.

           Returns:
               list[dict]: A list of dictionaries, each containing:
                   - code (str): The code of the language.
                   - language (str): The name of the language.
                   - daily_streak (int, optional): Current daily streak for the language (visible only to self or friends).
                   - max_streak (int, optional): Max streak for the language (visible only to self or friends).
                   - max_streak_date (str, optional): Date when the max streak was achieved at (visible only to self or friends).
        """
    friend = User.find_by_username(username)
    if friend is None:
        return []
    is_self_or_friend = friend.id == flask.g.user_id or Friendship.are_friends(flask.g.user_id, friend.id)
    return json_result(_serialize_language_streaks(friend.id, include_private=is_self_or_friend))


def _serialize_language_streaks(user_id: int, include_private: bool) -> list[dict]:
    user_languages = UserLanguage.query.filter_by(user_id=user_id).all()
    user_languages.sort(key=lambda ul: ul.max_streak or 0, reverse=True)
    result = []
    for ul in user_languages:
        obj = {
            "code": ul.language.code,
            "language": ul.language.name
        }
        if include_private:
            obj.update({
                "daily_streak": ul.current_daily_streak,
                "max_streak": ul.max_streak or 0,
                "max_streak_date": ul.max_streak_date.strftime("%Y-%m-%d") if ul.max_streak_date else None,
            })
        result.append(obj)
    return result
