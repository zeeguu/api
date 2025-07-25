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

    # Update reading completion on scroll events (always run for efficiency)
    if request.form.get("event") == "SCROLL" and request.form.get("article_id", None):
        _check_and_notify_article_completion_on_scroll(user, request.form)

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


def _check_and_notify_article_completion_on_scroll(user, form_data):
    """
    Update reading completion percentage and check for completion on every scroll event.
    This is much more efficient as it stores the completion percentage instead of recalculating.

    Args:
        user: The User who performed the scroll activity
        form_data: The form data from the scroll activity tracking request
    """
    try:
        from zeeguu.core.model import Article, UserArticle
        from zeeguu.core.behavioral_modeling import find_last_reading_percentage
        import json

        article_id = int(form_data.get("article_id"))
        article = Article.find_by_id(article_id)

        if not article:
            return

        # Get the reading percentage from the scroll data
        extra_data = form_data.get("extra_data", "")
        if not extra_data:
            return

        try:
            scroll_data = json.loads(extra_data)
            completion_percentage = find_last_reading_percentage(scroll_data)
        except (json.JSONDecodeError, Exception):
            return

        # Get or create UserArticle
        user_article = UserArticle.find_or_create(db_session, user, article)

        # Always update the reading completion percentage
        user_article.reading_completion = completion_percentage

        # Debug logging
        from zeeguu.logging import logp

        logp(
            f"[article_completion] Article {article_id} - completion: {completion_percentage:.2f}, completed_at: {user_article.completed_at}"
        )

        # Check if article is completed (>90%) and not already marked
        if completion_percentage > 0.9 and not user_article.completed_at:
            from datetime import datetime

            user_article.completed_at = datetime.now()

            # Send notification if enabled
            from flask import current_app

            if current_app.config.get("SEND_ARTICLE_COMPLETION_EMAILS", False):
                from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

                ZeeguuMailer.notify_article_completion(
                    user, article, completion_percentage
                )
        # Add to session to ensure updates are tracked
        db_session.add(user_article)

        db_session.commit()

    except Exception as e:
        # Don't fail the activity tracking if completion check fails
        from zeeguu.logging import logp

        logp(
            f"[article_completion] Failed to update reading completion on scroll: {str(e)}"
        )
        db_session.rollback()
