import flask
from sqlalchemy.orm import joinedload

from zeeguu.core.model import User
from zeeguu.core.model.user_metric import UserMetric
from zeeguu.core.model.badge import Badge
from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model.activity_type import ActivityType
from zeeguu.core.model.friend import Friend
from zeeguu.core.model.user_badge import UserBadge
from . import api, db_session


# ---------------------------------------------------------------------------
@api.route("/badges/count_not_shown", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_not_shown_user_badge_levels():
    """
    Return the number of user badge levels that the current user has achieved
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
    Retrieve all badges and their levels for the specified or current user.
    Each badge level includes achievement status and whether it has been shown.

    Returns:
    [
        {
           "name": "Translated Words",
           "description": "Translate {threshold} words while reading.",
           "levels": [
               {
                   "badge_level": 1,
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

    activity_types = ActivityType.query.options(joinedload(ActivityType.badges)).all()
    user_badges = UserBadge.find_all(used_user_id)
    achieved_map = {ub.badge_id: ub for ub in user_badges}
    user_metrics = UserMetric.find_all(used_user_id)
    progress_map = {um.activity_type_id: um for um in user_metrics}

    result = [serialize_activity_type(at, achieved_map, progress_map) for at in activity_types]

    return json_result(result)

# ---------------------------------------------------------------------------
@api.route("/badges/update_not_shown", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def update_not_shown_user_badge_levels():
    """
    Mark all unseen badge levels for the current user as shown.

    This updates all UserBadgeLevel records where:
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


def serialize_activity_type(activity_type: ActivityType, achieved_map: dict, progress_map: dict) -> dict:
    metric = progress_map.get(activity_type.id)
    levels = [
        serialize_badge(badge, achieved_map.get(badge.id))
        for badge in sorted(activity_type.badges, key=lambda b: b.level)
    ]

    return {
        "name": activity_type.name,
        "description": activity_type.description,
        "levels": levels,
        "current_value": metric.value if metric else 0,
    }


def serialize_badge(badge: Badge, user_badge: UserBadge | None) -> dict:
    return {
        "badge_level": badge.level,
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
