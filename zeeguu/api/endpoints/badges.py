from flask import request

from zeeguu.core.model.badge import BadgeCode
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
                "is_shown": level.is_shown
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


def update_badge_levels(badge_code: BadgeCode, user_id: int, current_value: int) -> list[UserBadgeLevel]:
    """
    Award all achievable badge levels a user doesn't have yet for a specific badge.

    Returns only newly created UserBadgeLevel objects.
    """
    badge = Badge.find(badge_code)
    if not badge:
        return []

    badge_level_ids = [
        level.id
        for level in BadgeLevel.find_all_achievable(badge_id=badge.id, current_value=current_value)
    ]

    if not badge_level_ids:
        return []

    user_badge_levels = UserBadgeLevel.find(user_id=user_id, badge_level_ids=badge_level_ids)
    owned_ids = {lvl.badge_level_id for lvl in user_badge_levels}

    missing_ids = set(badge_level_ids) - owned_ids
    created_badges: list[UserBadgeLevel] = []

    for level_id in missing_ids:
        new_badge = UserBadgeLevel(user_id=user_id, badge_level_id=level_id)
        db_session.add(new_badge)
        created_badges.append(new_badge)

    if missing_ids:
        db_session.commit()

    return created_badges
