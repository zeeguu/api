from datetime import datetime

from zeeguu.core.constants import (
    EVENT_USER_FEEDBACK,
    EVENT_LIKE_ARTICLE,
    EVENT_OPEN_ARTICLE,
)
from zeeguu.logging import log
from zeeguu.core.model import Article, UserArticle


def distill_article_interactions(session, user, data):
    """

        extracts info from user_activity_data

    :param session:
    :param event:
    :param value:
    :param user:
    """

    event = data["event"]
    value = data["value"]
    article_id = int(data["article_id"])

    log(f"event is: {event}")

    if EVENT_OPEN_ARTICLE in event:
        article_opened(session, article_id, user)
    elif EVENT_USER_FEEDBACK in event:
        article_feedback(session, article_id, user, value)
    """ elif EVENT_LIKE_ARTICLE in event:
        article_liked(session, article_id, user, value == "true") """


def article_feedback(session, article_id, user, event_value):
    from zeeguu.core.emailer.user_activity import send_notification_article_feedback

    nicer = {
        '"not_finished_for_broken"': "BROKEN",
        '"maybe_finish_later"': "Later",
        '"finished_difficulty_ok"': "OK",
        '"finished_difficulty_hard"': "HARD",
        '"finished_difficulty_easy"': "EASY",
        '"not_finished_for_other"': "Not Finished - OTHER",
        '"not_finished_for_boring"': "Not Finished - BORINNG",
        '"read_later"': "Read Later",
        '"not_finished_for_too_difficult"': "Not Finished - TOO DIFFICULT",
    }

    def beautify_article_feedback(feedback):
        return nicer.get(feedback, feedback)

    article = Article.query.filter_by(id=article_id).one()

    if (
        "broken"
        or "not_finished_for_broken"
        or "not_finished_for_incomplete"
        or "not_finished_for_other" in event_value
    ):
        article.vote_broken()
        session.add(article)
        session.commit()

    send_notification_article_feedback(
        beautify_article_feedback(event_value),
        user,
        article.title,
        article.url.as_string(),
        article.id,
    )


def article_liked(session, article_id, user, like_value):
    from zeeguu.core.emailer.user_activity import send_notification_article_feedback

    article = Article.query.filter_by(id=article_id).one()
    ua = UserArticle.find(user, article)
    ua.liked = like_value
    session.add(ua)
    session.commit()
    log(f"{ua}")
    send_notification_article_feedback(
        "Liked", user, article.title, article.url.as_string(), article.id
    )


def article_opened(session, article_id, user):
    article = Article.query.filter_by(id=article_id).one()
    ua = UserArticle.find(user, article)
    if not ua:
        ua = UserArticle.find_or_create(session, user, article, opened=datetime.now())
    ua.opened = datetime.now()
    session.add(ua)
    session.commit()
    log(f"{ua}")
