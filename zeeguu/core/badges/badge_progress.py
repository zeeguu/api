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

    badge_level_ids = db_session.scalars(
        db_session.query(BadgeLevel.id)
        .filter(
            BadgeLevel.badge_id == badge.id,
            BadgeLevel.target_value <= current_value
        )
        .order_by(BadgeLevel.level.asc())
    ).all()

    if not badge_level_ids:
        return []

    existing_levels = UserBadgeLevel.find(user_id=user_id, badge_level_ids=badge_level_ids)
    owned_ids = {lvl.badge_level_id for lvl in existing_levels}

    missing_ids = [lvl_id for lvl_id in badge_level_ids if lvl_id not in owned_ids]
    created_badges: list[UserBadgeLevel] = []

    for level_id in missing_ids:
        new_badge = UserBadgeLevel(user_id=user_id, badge_level_id=level_id)
        db_session.add(new_badge)
        created_badges.append(new_badge)

    return created_badges
