import flask
from sqlalchemy.orm import joinedload

from zeeguu.core.model.badge_level import BadgeLevel
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model.badge import Badge
from zeeguu.core.model.user_badge_level import UserBadgeLevel
from . import api, db_session


# ---------------------------------------------------------------------------
@api.route("/count_not_shown_badges", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_not_shown_badge_levels_for_user():
    """
    Return the number of user badge levels that the current user has achieved
    but have not yet been shown to them.
    """
    return json_result(UserBadgeLevel.count_user_not_shown(flask.g.user_id))


# ---------------------------------------------------------------------------
@api.route("/get_user_badges", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_badges_for_user():
    """
    Retrieve all badges and their levels for the current user.
    Each badge level includes achievement status and whether it has been shown.

    Returns:
    [
        {
           "badge_id": 1,
           "name": "Meaning Builder",
           "description": "Translate {target_value} words while reading.",
           "levels": [
               {
                   "badge_level": 1,
                   "target_value": 50,
                   "icon_url": "/icons/badge1.png",
                   "achieved": true,
                   "achieved_at": "2026-03-03T12:34:56",
                   "is_shown": false,
                   "name": "Beginner"
               }, ...]
        }, ... ]
    """
    user_id = flask.g.user_id

    badges = Badge.query.options(joinedload(Badge.badge_levels)).all()
    user_badge_levels = UserBadgeLevel.find_all(user_id)
    achieved_map = {ubl.badge_level_id: ubl for ubl in user_badge_levels}

    result = [serialize_badge(badge, achieved_map) for badge in badges]

    UserBadgeLevel.update_not_shown_for_user(db_session, user_id)
    db_session.commit()

    return json_result(result)


def serialize_badge(badge: Badge, achieved_map: dict) -> dict:
    levels = [
        serialize_badge_level(level, achieved_map.get(level.id))
        for level in sorted(badge.badge_levels, key=lambda b: b.level)
    ]

    return {
        "badge_id": badge.id,
        "name": badge.name,
        "description": badge.description,
        "levels": levels,
    }


def serialize_badge_level(level: BadgeLevel, user_level: UserBadgeLevel | None) -> dict:
    return {
        "badge_level": level.level,
        "target_value": level.target_value,
        "icon_url": level.icon_url,
        "achieved": user_level is not None,
        "achieved_at": (
            user_level.achieved_at.isoformat()
            if user_level and user_level.achieved_at
            else None
        ),
        "is_shown": user_level.is_shown if user_level else False,
        "name": level.name,
    }
