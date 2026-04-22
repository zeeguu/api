import flask
from sqlalchemy.orm import joinedload

from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import User
from zeeguu.core.model.badge_category import BadgeCategory
from zeeguu.core.model.badge import Badge
from zeeguu.core.model.friend import Friend
from zeeguu.core.model.user_badge import UserBadge
from zeeguu.core.model.user_badge_progress import UserBadgeProgress
from . import api, db_session


# ---------------------------------------------------------------------------
@api.route("/badges/count_not_shown", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_not_shown_user_badge_levels():
    """
    Return the number of UserBadge entries that the current user has achieved
    but have not yet been shown to them.
    """
    return json_result(UserBadge.count_user_not_shown(flask.g.user_id))


# ---------------------------------------------------------------------------
@api.route("/badges", methods=["GET"])
@api.route("/badges/<username>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_badges_for_user(username: str = None):
    """
    Retrieve all activity types and their corresponding badges for the specified or current user.
    Each badge includes achievement status and whether it has been shown.

    Returns:
    [
        {
           "name": "Translated Words",
           "description": "Translate {threshold} words while reading.",
           "badges": [
               {
                   "level": 1,
                   "name": "Word Explorer",
                   "threshold": 50,
                   "icon_name": "/badge1.svg",
                   "achieved": true,
                   "achieved_at": "2026-03-03T12:34:56",
                   "is_shown": false
               }, ...]
           "current_value": 10
        }, ... ]
    """
    requester_id = flask.g.user_id
    if username is not None:
        used_user = User.find_by_username(username)
        if used_user is None:
            return []
        used_user_id = used_user.id
        if requester_id != used_user_id and not Friend.are_friends(requester_id, used_user_id):
            return make_error(403, "You can only view badges for yourself or your friends.")
    else:
        used_user_id = requester_id

    badge_categories = BadgeCategory.query.options(joinedload(BadgeCategory.badges)).all()
    user_badges = UserBadge.find_all(used_user_id)
    achieved_map = {ub.badge_id: ub for ub in user_badges}
    user_badge_progress_list = UserBadgeProgress.find_all(used_user_id)
    progress_map = {um.badge_category_id: um for um in user_badge_progress_list}

    result = [serialize_badge_category(at, achieved_map, progress_map) for at in badge_categories]

    return json_result(result)


# ---------------------------------------------------------------------------
@api.route("/badges/update_not_shown", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def update_not_shown_user_badge_levels():
    """
    Mark all unseen badges for the current user as shown.

    This updates all UserBadge records where:
        - user_id matches the current user
        - is_shown is False

    Returns:
    {
        "updated": true
    }
    """
    UserBadge.update_not_shown_for_user(db_session, flask.g.user_id)
    db_session.commit()

    return json_result({"updated": True})


def serialize_badge_category(badge_category: BadgeCategory, achieved_map: dict, progress_map: dict) -> dict:
    metric = progress_map.get(badge_category.id)
    badges = [
        serialize_badge(badge, achieved_map.get(badge.id))
        for badge in sorted(badge_category.badges, key=lambda b: b.level)
    ]

    return {
        "name": badge_category.name,
        "badges": badges,
        "current_value": metric.value if metric else 0,
    }


def serialize_badge(badge: Badge, user_badge: UserBadge | None) -> dict:
    return {
        "level": badge.level,
        "name": badge.name,
        "description": badge.description,
        "threshold": badge.threshold,
        "icon_name": badge.icon_name,
        "achieved": user_badge is not None,
        "achieved_at": (
            user_badge.achieved_at.isoformat()
            if user_badge and user_badge.achieved_at
            else None
        ),
        "is_shown": user_badge.is_shown if user_badge else False
    }
