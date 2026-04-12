from zeeguu.core.model.activity_type import ActivityTypeMetric, ActivityType, BadgeType
from zeeguu.core.model.badge import Badge
from zeeguu.core.model.user_badge import UserBadge
from zeeguu.core.model.user_metric import UserMetric
from zeeguu.logging import log


def process_badge_event(
        db_session,
        metric: ActivityTypeMetric,
        user_id: int,
        increment_value: int = 1,
        current_value: int | None = None,
) -> list[UserBadge]:
    """
        Route badge progress updates based on activity_type.badge_type.

        COUNTER: increment metric by increment_value.
        GAUGE: overwrite metric with current_value.
        ONE_TIME: mark metric as 1 (or current_value if provided).

        After updating the corresponding UserMetric value, also creates
        UserBadge entries for all newly achieved badges.

        Returns newly created UserBadge records.
    """
    activity_type = ActivityType.find(metric)
    if not activity_type:
        log(f"[BADGE-ERROR] Cannot find activity type with metric='{metric}'")
        return []

    if activity_type.badge_type == BadgeType.COUNTER:
        user_metric = _increment_user_metric(db_session, user_id, activity_type.id, increment_value)
    elif activity_type.badge_type == BadgeType.GAUGE:
        if current_value is None:
            log(f"[BADGE-ERROR] Gauge activity '{metric}' requires current_value in process_badge_event")
            return []
        user_metric = _update_user_metric(db_session, user_id, activity_type.id, current_value)
    elif activity_type.badge_type == BadgeType.ONE_TIME:
        resolved_value = current_value if current_value is not None else 1
        user_metric = _update_user_metric(db_session, user_id, activity_type.id, resolved_value)
    else:
        log(f"[BADGE-ERROR] Unsupported badge_type='{activity_type.badge_type}' for metric='{metric}'")
        return []

    return _award_badges(
        db_session,
        activity_type.id,
        user_id,
        user_metric.value,
    )


def _increment_user_metric(db_session, user_id: int, activity_type_id: int, increment: int = 1) \
        -> UserMetric:
    """
        Increment a user's metric by the given value.

        Returns the updated UserMetric.
    """
    return UserMetric.create_or_increment(
        db_session,
        user_id,
        activity_type_id,
        increment,
    )


def _update_user_metric(db_session, user_id, activity_type_id: int, current_value: int) \
        -> UserMetric:
    """
        Update and overwrite a user's metric with the given value.

        Returns the updated UserMetric.
    """
    return UserMetric.create_or_update(
        db_session,
        user_id,
        activity_type_id,
        current_value,
    )


def _award_badges(db_session, activity_type_id: int, user_id: int, current_value: int) -> list[UserBadge]:
    """
       Create UserBadge entries for all newly achieved badges.
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
