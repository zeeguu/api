import flask


from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api, db_session
from .exercises import scheduled_bookmarks_to_study
from zeeguu.core.model.user_notification import UserNotification
from zeeguu.core.model.notification import Notification
from zeeguu.core.model.user import User
from zeeguu.core.content_recommender.elastic_recommender import (
    article_recommendations_for_user,
)
from zeeguu.core.model.session import Session
from datetime import datetime, timedelta

NOTIFICATION_TYPES = {
    "EXERCISES": {
        "message": "You have exercises scheduled for today!",
        "url": "/exercises",
    },
    "ARTICLES": {
        "message": "You have new articles for your topics!",
        "url": "/articles",
    },
    "DAILY_LOGIN": {
        "message": "Try reading an article with Zeeguu!",
        "url": "/artivles",
    },
}


@api.route("/get_notification_for_user", methods=["GET"])
@cross_domain
@requires_session
def get_notification_for_user():
    """
    For now, we try to check if the user has any scheduled bookmarks
    to practice. Otherwise, we will invite the user to check articles.
    """
    notification_data = {}
    notification_data["notification_available"] = True
    user = User.find_by_id(flask.g.user_id)
    # Is there exercises for user?
    if scheduled_bookmarks_to_study(1):
        user_notification = UserNotification.create_user_notification(
            user.id, Notification.EXERCISE_AVAILABLE, db_session
        )
        db_session.commit()
        notification_data.update(NOTIFICATION_TYPES["EXERCISES"])
        notification_data["user_notification_id"] = user_notification.id
        return json_result(notification_data)

    # Is there new articles for the user?
    articles = article_recommendations_for_user(user, 3)
    last_activity_date_for_user = Session.get_last_use_for_user(user.id)
    if any([a.published_time > last_activity_date_for_user for a in articles]):
        user_notification = UserNotification.create_user_notification(
            user.id, Notification.NEW_ARTICLE_AVAILABLE, db_session
        )
        db_session.commit()
        notification_data.update(NOTIFICATION_TYPES["ARTICLES"])
        notification_data["user_notification_id"] = user_notification.id
        return json_result(notification_data)

    # Daily login
    if (datetime.now() - last_activity_date_for_user).days >= 1:
        user_notification = UserNotification.create_user_notification(
            user.id, Notification.DAILY_LOGIN, db_session
        )
        db_session.commit()
        notification_data.update(NOTIFICATION_TYPES["DAILY_LOGIN"])
        notification_data["user_notification_id"] = user_notification.id
        return json_result(notification_data)

    notification_data["notification_available"] = False
    return json_result(notification_data)


@api.route("/set_notification_click_date", methods=["POST"])
@cross_domain
@requires_session
def set_notification_click_date():
    data = flask.request.form
    # user = User.find_by_id(flask.g.user_id)
    user_notification_id = data.get("user_notification_id", None)
    UserNotification.update_user_notification_time(user_notification_id, db_session)
    db_session.commit()

    return "OK"
