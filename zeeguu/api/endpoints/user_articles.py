import flask

from zeeguu.core.content_recommender import article_recommendations_for_user, topic_filter_for_user
from zeeguu.core.model import UserArticle, Article, PersonalCopy

from zeeguu.api.utils.route_wrappers import cross_domain, with_session
from zeeguu.api.utils.json_result import json_result
from . import api

from flask import request


# ---------------------------------------------------------------------------
@api.route("/user_articles/recommended", methods=("GET",))
@api.route("/user_articles/recommended/<int:count>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def user_articles_recommended(count: int = 20):
    """
    recommendations for all languages
    """

    try:
        articles = article_recommendations_for_user(flask.g.user, count)
    except:
        # we failed to get recommendations from elastic
        # return something 
        articles = Article.query.filter_by(broken=0).filter_by(language_id=flask.g.user.learned_language_id).order_by(
            Article.published_time.desc()).limit(20)

    article_infos = [UserArticle.user_article_info(flask.g.user, a) for a in articles]

    return json_result(article_infos)


@api.route("/user_articles/saved", methods=["GET"])
@cross_domain
@with_session
def saved_articles():
    saves = PersonalCopy.all_for(flask.g.user)

    article_infos = [
        UserArticle.user_article_info(flask.g.user, e) for e in saves
    ]

    return json_result(article_infos)


# ---------------------------------------------------------------------------
@api.route("/user_articles/topic_filtered", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def user_articles_topic_filtered():
    """
    recommendations based on filters coming from the UI
    """
    MAX_ARTICLES_PER_TOPIC = 20

    topic = request.form.get("topic")
    newer_than = request.form.get("newer_than", None)
    media_type = request.form.get("media_type", None)
    max_duration = request.form.get("max_duration", None)
    min_duration = request.form.get("min_duration", None)
    difficulty_level = request.form.get("difficulty_level", None)

    articles = topic_filter_for_user(flask.g.user, MAX_ARTICLES_PER_TOPIC, newer_than,
                                     media_type, max_duration, min_duration, difficulty_level, topic)
    article_infos = [UserArticle.user_article_info(flask.g.user, a) for a in articles]

    return json_result(article_infos)


# ---------------------------------------------------------------------------
@api.route("/user_articles/starred_or_liked", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def user_articles_starred_and_liked():
    return json_result(
        UserArticle.all_starred_and_liked_articles_of_user_info(flask.g.user)
    )


# ---------------------------------------------------------------------------
@api.route("/cohort_articles", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def user_articles_cohort():
    """
    get all articles for the cohort associated with the user
    """

    return json_result(flask.g.user.cohort_articles_for_user())
