from zeeguu.core.model.user_badge_progress import UserBadgeProgress
from zeeguu.core.model.badge import BadgeCode, Badge
from zeeguu.core.model.badge_level import BadgeLevel
from zeeguu.core.model.user_badge_level import UserBadgeLevel


def _award_badge_levels(db_session, badge_id: int, user_id: int, current_value: int) -> list[UserBadgeLevel]:
    """
       Create UserBadgeLevel entries for all newly achieved levels.
       Returns only newly created levels.
    """
    badge_level_ids = db_session.scalars(
        db_session.query(BadgeLevel.id)
        .filter(
            BadgeLevel.badge_id == badge_id,
            BadgeLevel.target_value <= current_value
        )
        .order_by(BadgeLevel.level.asc())
    ).all()

    if not badge_level_ids:
        return []

    existing_levels = UserBadgeLevel.find(user_id=user_id, badge_level_ids=badge_level_ids)
    owned_ids = {lvl.badge_level_id for lvl in existing_levels}

    missing_ids = [lvl_id for lvl_id in badge_level_ids if lvl_id not in owned_ids]

    created_badges = [
        UserBadgeLevel(user_id=user_id, badge_level_id=level_id)
        for level_id in missing_ids
    ]

    db_session.add_all(created_badges)

    return created_badges


def increment_badge_progress(db_session, badge_code: BadgeCode, user_id: int, increment_value: int = 1) \
        -> list[UserBadgeLevel]:
    """
        Increment a user's badge progress and award newly achieved levels.
        Returns newly created UserBadgeLevel records.
    """
    badge = Badge.find(badge_code)
    if not badge:
        return []

    progress = UserBadgeProgress.create_or_increment(
        db_session,
        user_id,
        badge.id,
        increment_value
    )

    return _award_badge_levels(
        db_session,
        badge.id,
        user_id,
        progress.current_value
    )


def update_badge_progress(db_session, badge_code: BadgeCode, user_id: int, current_value: int) \
        -> list[UserBadgeLevel]:
    """
        Overwrite a user's badge progress and award newly achieved levels.
        Returns newly created UserBadgeLevel records.
    """
    badge = Badge.find(badge_code)
    if not badge:
        return []

    progress = UserBadgeProgress.create_or_update(
        db_session,
        user_id,
        badge.id,
        current_value
    )

    return _award_badge_levels(
        db_session,
        badge.id,
        user_id,
        progress.current_value
    )
