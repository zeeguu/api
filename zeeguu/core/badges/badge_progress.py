from zeeguu.core.model.badge import BadgeCode, Badge
from zeeguu.core.model.badge_level import BadgeLevel
from zeeguu.core.model.user_badge_level import UserBadgeLevel


def update_badge_levels(db_session, badge_code: BadgeCode, user_id: int, current_value: int) -> list[UserBadgeLevel]:
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

    return created_badges