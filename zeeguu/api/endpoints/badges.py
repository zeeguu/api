from flask import request

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
    badges = Badge.query.all()
    user_badge_levels = UserBadgeLevel.find_all(user_id)
    achieved_map = {ubl.badge_level_id: ubl for ubl in user_badge_levels}
    result = []
    for badge in badges:
        badge_levels = []
        for badge_level in badge.badge_levels:
            achieved = badge_level.id in achieved_map
            achieved_at = achieved_map[badge_level.id].achieved_at if achieved else None
            badge_levels.append({
                "badge_level": badge_level.level,
                "target_value": badge_level.target_value,
                "icon_url": badge_level.icon_url,
                "achieved": achieved,
                "achieved_at": achieved_at.isoformat() if achieved_at else None,
                "is_shown": badge_level.is_shown
            })
        result.append({
            "badge_id": badge.id,
            "name": badge.name,
            "description": badge.description,
            "levels": badge_levels,
        })
    return json_result(result)


## Update badge progress endpoint (not implemented yet)
# ---------------------------------------------------------------------------
@api.route("/update_badge_progress", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
# @requires_session
def update_badge_progress():
    # For badge id
    badge_id = request.form.get("badge_id")
    user_id = request.form.get("user_id")

    # Validation of inputs
    if not badge_id or not user_id:
        return json_result({"error": "Missing badge_id or user_id"}, status=400)

    # Get current progress for the badge and user
    user_badge_level = UserBadgeLevel.query.filter_by(badge_id=badge_id, user_id=user_id).first()
    if not user_badge_level:
        return json_result({"error": "User badge level not found"}, status=404)

