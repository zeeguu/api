import flask
from flask import request
from zeeguu.core.model.badge import Badge, BadgeLevel, UserBadgeLevel 
from zeeguu.core.model.article_topic_user_feedback import ArticleTopicUserFeedback
from zeeguu.api.utils.json_result import json_result
from zeeguu.core.model.personal_copy import PersonalCopy
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api, db_session
from zeeguu.core.model.article import HTML_TAG_CLEANR

import re
from langdetect import detect
import json
from zeeguu.logging import log
# ---------------------------------------------------------------------------
@api.route("/badges/<int:user_id>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
# @requires_session
def get_badges_for_user(user_id: int):
    
    # Get all badge levels achieved by the user
    badges = Badge.query.all()
    badge_levels = BadgeLevel.query.all()
    user_badge_levels = UserBadgeLevel.query.filter_by(user_id=user_id).all()
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

