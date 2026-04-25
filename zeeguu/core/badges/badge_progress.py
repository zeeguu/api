from zeeguu.core.model.badge import Badge
from zeeguu.core.model.badge_category import ActivityMetric, BadgeCategory, AwardMechanism
from zeeguu.core.model.user_badge import UserBadge
from zeeguu.core.model.user_badge_progress import UserBadgeProgress
from zeeguu.logging import log


def update_metric_and_award_badges(
        db_session,
        metric: ActivityMetric,
        user_id: int,
        value: int = 1
) -> list[UserBadge]:
    """
        Route badge progress updates based on badge_category.award_mechanism.

        COUNTER: increment metric by value.
        GAUGE: overwrite metric with value.
        ONE_TIME: mark metric as 1 (or value if provided).

        After updating the corresponding UserBadgeProgress value,
        also creates UserBadge entries for all newly achieved badges.

        Returns newly created UserBadge records.
    """
    badge_category = BadgeCategory.find(metric)
    if not badge_category:
        log(f"[BADGE-ERROR] Cannot find badge category with metric='{metric}'")
        return []

    if badge_category.award_mechanism == AwardMechanism.COUNTER:
        user_badge_progress = _increment_user_badge_progress(db_session, user_id, badge_category.id, value)
    elif badge_category.award_mechanism == AwardMechanism.GAUGE:
        user_badge_progress = _update_user_badge_progress(db_session, user_id, badge_category.id, value)
    elif badge_category.award_mechanism == AwardMechanism.ONE_TIME:
        user_badge_progress = _update_user_badge_progress(db_session, user_id, badge_category.id, value)
    else:
        log(f"[BADGE-ERROR] Unsupported award_mechanism='{badge_category.award_mechanism}' for metric='{metric}'")
        return []

    return _award_new_badges(
        db_session,
        badge_category.id,
        user_id,
        user_badge_progress.value,
    )


def _increment_user_badge_progress(db_session, user_id: int, badge_category_id: int, increment: int = 1) \
        -> UserBadgeProgress:
    """
        Increment a user's metric by the given value.

        Returns the updated UserBadgeProgress.
    """
    return UserBadgeProgress.create_or_increment(
        db_session,
        user_id,
        badge_category_id,
        increment,
    )


def _update_user_badge_progress(db_session, user_id, badge_category_id: int, current_value: int) \
        -> UserBadgeProgress:
    """
        Update and overwrite a user's metric with the given value.

        Returns the updated UserBadgeProgress.
    """
    return UserBadgeProgress.create_or_update(
        db_session,
        user_id,
        badge_category_id,
        current_value,
    )


def _award_new_badges(db_session, badge_category_id: int, user_id: int, current_value: int) -> list[UserBadge]:
    """
       Create UserBadge entries for all newly achieved badges.
       Returns only newly created entries.
    """
    from sqlalchemy import select
    badge_ids = db_session.scalars(
        select(Badge.id).where(
            Badge.badge_category_id == badge_category_id,
            Badge.threshold <= current_value
        ).order_by(Badge.level.asc())
    ).all()

    if not badge_ids:
        return []

    existing = UserBadge.find(user_id=user_id, badge_ids=badge_ids)
    owned_ids = {ub.badge_id for ub in existing}

    missing_ids = [bid for bid in badge_ids if bid not in owned_ids]

    created = [
        UserBadge(user_id=user_id, badge_id=badge_id)
        for badge_id in missing_ids
    ]

    db_session.add_all(created)

    return created
