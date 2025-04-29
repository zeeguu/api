import flask

from zeeguu.core.content_recommender import (
    article_recommendations_for_user,
    topic_filter_for_user,
    content_recommendations,
    video_recommendations_for_user,
)
from zeeguu.core.model import UserArticle, Article, PersonalCopy, User, Video

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from sentry_sdk import capture_exception
from . import api

from random import random

from flask import request

MAX_ARTICLES_PER_TOPIC = 20


# ---------------------------------------------------------------------------
@api.route("/user_articles/recommended", methods=("GET",))
@api.route("/user_articles/recommended/<int:count>", methods=("GET",))
@api.route("/user_articles/recommended/<int:count>/<int:page>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_recommended(count: int = 15, page: int = 0):
    """
    Home Page recomendation for the users.

    It prioritizes Difficulty and Recency so the users see
    new articles every day.

    It also includes articles from user's search subscriptions if they
    are relevant enough. The articles are then sorted by published date.

    """

    def mix_articles_with_videos(articles, videos):
        """
        Mixes articles with the videos by placing them in random positions
        +-2 the positon of the lat placed video + the index of the video.

        This naturally increases the distance between the videos.
        Some examples of video positions:
            - [0, 1, 4, 8, 12], [0, 2, 4, 9, 15], [1, 3, 5, 8, 13], [2, 4, 7, 12, 17]
        """
        final_result = []
        last_placed_video = 0
        for v_i, video in enumerate(videos):
            video_pos_i = last_placed_video + int(round(random() * 2) + (v_i))
            final_result += articles[last_placed_video:video_pos_i] + [video]
            last_placed_video = video_pos_i
        final_result += articles[last_placed_video:]
        return final_result

    user = User.find_by_id(flask.g.user_id)
    try:
        articles = article_recommendations_for_user(user, count, page)
        videos = video_recommendations_for_user(user, 5, page)
        print("Total Videos found: ", len(videos))
        print("Total Articles found: ", len(articles))
    except Exception as e:
        import traceback

        # we failed to get recommendations from elastic
        # return something
        print(e)
        print(traceback.format_exc())
        articles = (
            Article.query.filter_by(broken=0)
            .filter_by(language_id=user.learned_language_id)
            .order_by(Article.published_time.desc())
            .limit(20)
        )

        videos = (
            Video.query.filter_by(broken=0)
            .filter_by(language_id=user.learned_language_id)
            .order_by(Video.published_time.desc())
            .limit(3)
        )

    article_infos = [UserArticle.user_article_info(user, a) for a in articles]
    video_infos = [v.video_info() for v in videos if v]
    combined_results = mix_articles_with_videos(article_infos, video_infos)
    return json_result(combined_results)


@api.route("/user_articles/saved", methods=["GET"])
@api.route("/user_articles/saved/<int:page>", methods=["GET"])
@cross_domain
@requires_session
def saved_articles(page: int = None):
    user = User.find_by_id(flask.g.user_id)
    if page is not None:
        saves = PersonalCopy.get_page_for(user, page)
    else:
        saves = PersonalCopy.all_for(user)

    article_infos = [UserArticle.user_article_info(user, e) for e in saves]

    return json_result(article_infos)


@cross_domain
@requires_session
def saved_articles():
    user = User.find_by_id(flask.g.user_id)
    saves = PersonalCopy.all_for(user)

    article_infos = [UserArticle.user_article_info(user, e) for e in saves]

    return json_result(article_infos)


# ---------------------------------------------------------------------------
@api.route("/user_articles/topic_filtered", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_topic_filtered():
    """
    recommendations based on filters coming from the UI
    """

    topic = request.form.get("topic")
    newer_than = request.form.get("newer_than", None)
    media_type = request.form.get("media_type", None)
    max_duration = request.form.get("max_duration", None)
    min_duration = request.form.get("min_duration", None)
    difficulty_level = request.form.get("difficulty_level", None)
    user = User.find_by_id(flask.g.user_id)

    articles = topic_filter_for_user(
        user,
        MAX_ARTICLES_PER_TOPIC,
        newer_than,
        media_type,
        max_duration,
        min_duration,
        difficulty_level,
        topic,
    )
    article_infos = [UserArticle.user_article_info(user, a) for a in articles]

    return json_result(article_infos)


# ---------------------------------------------------------------------------
@api.route("/user_articles/starred_or_liked", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_starred_and_liked():
    user = User.find_by_id(flask.g.user_id)
    return json_result(UserArticle.all_starred_and_liked_articles_of_user_info(user))


# ---------------------------------------------------------------------------
@api.route("/cohort_articles", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_cohort():
    """
    get all articles for the cohort associated with the user
    """
    user = User.find_by_id(flask.g.user_id)
    return json_result(user.cohort_articles_for_user())


# ---------------------------------------------------------------------------
@api.route("/user_articles/foryou", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_articles_foryou():
    article_infos = []
    user = User.find_by_id(flask.g.user_id)
    try:
        articles = content_recommendations(user.id, user.learned_language_id)
        print("Sending CB recommendations")
    except Exception as e:
        import traceback

        traceback.print_exc()
        print("Failed with: ", e)
        capture_exception(e)
        # Usually no recommendations when the user has not liked any articles
        articles = []
    article_infos = [UserArticle.user_article_info(user, a) for a in articles]

    return json_result(article_infos)
