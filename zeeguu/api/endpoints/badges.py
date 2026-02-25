import flask
from flask import request
from zeeguu.core.model.badge import Badge
from zeeguu.core.model.badge_level import BadgeLevel
from zeeguu.core.model.user_badge_level import UserBadgeLevel
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api, db_session


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
        levels = []
        for level in badge.levels:  # Assuming Badge has a .levels relationship
            achieved = level.id in achieved_map
            achieved_at = achieved_map[level.id].achieved_at if achieved else None
            levels.append({
                "level": level.level,
                "target_value": level.target_value,
                "icon_url": level.icon_url,
                "achieved": achieved,
                "achieved_at": achieved_at.isoformat() if achieved_at else None,
            })
        result.append({
            "badge_id": badge.id,
            "name": badge.name,
            "description": badge.description,
            "levels": levels,
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


def check_badge_level(badge_id: int, user_id: int, current_value: int) -> UserBadgeLevel:
    user_badge_level = UserBadgeLevel.find(user_id=user_id, badge_id=badge_id)
    if not user_badge_level:
        next_badge_level = BadgeLevel.find(badge_id=badge_id, level=1)
    else:
        next_badge_level = BadgeLevel.find(badge_id=badge_id, level=user_badge_level.badge_level.level + 1)
    if not next_badge_level:
        return None
    if current_value >= next_badge_level.target_value:
        return UserBadgeLevel.create(user_id=user_id, badge_level_id=next_badge_level.id)
    return user_badge_level
