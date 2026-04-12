from zeeguu.core.model.user_metric import UserMetric
from zeeguu.core.model.activity_type import MetricKey, ActivityType
from zeeguu.core.model.badge import Badge
from zeeguu.core.model.user_badge import UserBadge
from zeeguu.logging import log


def _award_badges(db_session, activity_type_id: int, user_id: int, current_value: int) -> list[UserBadge]:
    """
       Create UserBadge entries for all newly achieved badge levels.
       Returns only newly created entries.
    """
    badge_ids = db_session.scalars(
        db_session.query(Badge.id)
        .filter(
            Badge.activity_type_id == activity_type_id,
            Badge.threshold <= current_value
        )
        .order_by(Badge.level.asc())
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


def increment_badge_progress(db_session, metric_key: MetricKey, user_id: int, increment_value: int = 1) \
        -> list[UserBadge]:
    """
        Increment a user's metric and award newly achieved badges.
        Returns newly created UserBadge records.
    """
    activity_type = ActivityType.find(metric_key)
    if not activity_type:
        log(f"[BADGE-ERROR] Cannot find activity type with metric_key='{metric_key}'")
        return []

    metric = UserMetric.create_or_increment(
        db_session,
        user_id,
        activity_type.id,
        increment_value
    )

    return _award_badges(
        db_session,
        activity_type.id,
        user_id,
        metric.value
    )


def update_badge_progress(db_session, metric_key: MetricKey, user_id: int, current_value: int) \
        -> list[UserBadge]:
    """
        Overwrite a user's metric and award newly achieved badges.
        Returns newly created UserBadge records.
    """
    activity_type = ActivityType.find(metric_key)
    if not activity_type:
        log(f"[BADGE-ERROR] Cannot find activity type with metric_key='{metric_key}'")
        return []

    metric = UserMetric.create_or_update(
        db_session,
        user_id,
        activity_type.id,
        current_value
    )

    return _award_badges(
        db_session,
        activity_type.id,
        user_id,
        metric.value
    )
