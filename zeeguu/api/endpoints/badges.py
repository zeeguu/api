import flask
from sqlalchemy.orm import joinedload

from zeeguu.core.model.user_badge_progress import UserBadgeProgress
from zeeguu.core.model.badge_level import BadgeLevel
from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model.badge import Badge
from zeeguu.core.model.friend import Friend
from zeeguu.core.model.user_badge_level import UserBadgeLevel
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
    return json_result(UserBadgeLevel.count_user_not_shown(flask.g.user_id))


# ---------------------------------------------------------------------------
@api.route("/badges", methods=["GET"])
@api.route("/badges/<int:user_id>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_badges_for_user(user_id: int = None):
    """
    Retrieve all badges and their levels for the specified or current user.
    Each badge level includes achievement status and whether it has been shown.

    Returns:
    [
        {
           "badge_id": 1,
           "name": "Meaning Builder",
           "description": "Translate {target_value} words while reading.",
           "levels": [
               {
                   "badge_level": 1,
                   "target_value": 50,
                   "icon_name": "/badge1.svg",
                   "achieved": true,
                   "achieved_at": "2026-03-03T12:34:56",
                   "is_shown": false,
                   "name": "Beginner"
               }, ...]
           "current_value": 10
        }, ... ]
    """
    requester_id = flask.g.user_id
    used_user_id = user_id if user_id is not None else requester_id

    if used_user_id != requester_id and not Friend.are_friends(requester_id, used_user_id):
        return make_error(403, "You can only view badges for yourself or your friends.")

    badges = Badge.query.options(joinedload(Badge.badge_levels)).all()
    user_badge_levels = UserBadgeLevel.find_all(used_user_id)
    achieved_map = {ubl.badge_level_id: ubl for ubl in user_badge_levels}
    user_badge_progress = UserBadgeProgress.find_all(used_user_id)
    progress_map = {ubp.badge_id: ubp for ubp in user_badge_progress}

    result = [serialize_badge(badge, achieved_map, progress_map) for badge in badges]

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
    UserBadgeLevel.update_not_shown_for_user(db_session, flask.g.user_id)
    db_session.commit()

    return json_result({"updated": True})


def serialize_badge(badge: Badge, achieved_map: dict, progress_map: dict) -> dict:
    progress = progress_map.get(badge.id)
    levels = [
        serialize_badge_level(level, achieved_map.get(level.id))
        for level in sorted(badge.badge_levels, key=lambda b: b.level)
    ]

    return {
        "badge_id": badge.id,
        "name": badge.name,
        "description": badge.description,
        "levels": levels,
        "current_value": progress.current_value if progress else 0,
    }


def serialize_badge_level(level: BadgeLevel, user_level: UserBadgeLevel | None) -> dict:
    return {
        "badge_level": level.level,
        "target_value": level.target_value,
        "icon_name": level.icon_name,
        "achieved": user_level is not None,
        "achieved_at": (
            user_level.achieved_at.isoformat()
            if user_level and user_level.achieved_at
            else None
        ),
        "is_shown": user_level.is_shown if user_level else False,
        "name": level.name,
    }
