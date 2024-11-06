import flask
from flask import request
from zeeguu.core.user_activity_hooks.article_interaction_hooks import (
    distill_article_interactions,
)

from . import api, db_session
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import UserActivityData, User


@api.route("/upload_user_activity_data", methods=["POST"])
@cross_domain
@requires_session
def upload_user_activity_data():
    """

        The user needs to be logged in, so the event
        refers to themselves. Thus there is no need
        for submitting a user id.

        There are four elements that can be submitted for
        an user activity event. Within an example they are:

                time: '2016-05-05T10:11:12',
                event: "User Read Article",
                value: "300s",
                extra_data: "{article_source: 2, ...}"

        All these four elements have to be submitted as POST
        arguments

    :return: OK if all went well
    """
    user = User.find_by_id(flask.g.user_id)
    UserActivityData.create_from_post_data(db_session, request.form, user)

    if request.form.get("article_id", None):
        distill_article_interactions(db_session, user, request.form)

    if request.form.get("event") == "AUDIO_EXP":
        from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

        ZeeguuMailer.notify_audio_experiment(request.form, user)

    return "OK"


@api.route("/days_since_last_use", methods=["GET"])
@cross_domain
@requires_session
def days_since_last_use():
    """
    Returns the number of days since the last user activity event
    or an empty string in case there is no user activity event.
    """

    from datetime import datetime

    last_active_time = UserActivityData.get_last_activity_timestamp(flask.g.user_id)

    if last_active_time:
        time_difference = datetime.now() - last_active_time
        return str(time_difference.days)

    return ""
