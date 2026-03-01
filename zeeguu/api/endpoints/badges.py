from flask import request
from sqlalchemy.orm import joinedload

from zeeguu.core.model.badge import Badge
from zeeguu.core.model.user_badge_level import UserBadgeLevel
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api


# ---------------------------------------------------------------------------
@api.route("/badges/<int:user_id>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
# @requires_session
def get_badges_for_user(user_id: int):
    # Get all badge levels achieved by the user
    badges = (
        Badge.query
        .options(joinedload(Badge.badge_levels))
        .all()
    )
    user_badge_levels = UserBadgeLevel.find_all(user_id)
    achieved_map = {ubl.badge_level_id: ubl for ubl in user_badge_levels}
    result = []
    for badge in badges:
        badge_levels = []
        for badge_level in sorted(badge.badge_levels, key=lambda b: b.level):
            achieved = badge_level.id in achieved_map
            achieved_at = achieved_map[badge_level.id].achieved_at if achieved else None
            badge_levels.append({
                "badge_level": badge_level.level,
                "target_value": badge_level.target_value,
                "icon_url": badge_level.icon_url,
                "achieved": achieved,
                "achieved_at": achieved_at.isoformat() if achieved_at else None,
                "is_shown": achieved_map[badge_level.id].is_shown if achieved else False,
                "name": badge_level.name
            })
        result.append({
            "badge_id": badge.id,
            "name": badge.name,
            "description": badge.description,
            "levels": badge_levels,
        })
    return json_result(result)

# ---------------------------------------------------------------------------
@api.route("/badges/<int:user_id>/not_shown", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
# @requires_session
def get_not_shown_badge_levels_for_user(user_id: int):
    return json_result(UserBadgeLevel.count_user_not_shown(user_id))


