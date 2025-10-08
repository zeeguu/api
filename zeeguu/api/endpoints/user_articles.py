import flask

from zeeguu.core.content_recommender import (
    article_recommendations_for_user,
    topic_filter_for_user,
    content_recommendations,
    get_user_info_from_content_recommendations,
)
from zeeguu.core.model import (
    UserArticle,
    Article,
    PersonalCopy,
    User,
    UserArticleBrokenReport,
)

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from sentry_sdk import capture_exception
from . import api


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

    URL parameters:
    - exclude_saved: if 'true', exclude saved articles from results

    Note: Hidden articles are always excluded from recommendations.
    """

    user = User.find_by_id(flask.g.user_id)

    # Get exclusion parameters from request args
    exclude_saved = request.args.get("exclude_saved", "false").lower() == "true"

    # Collect article IDs to exclude
    articles_to_exclude = []

    if exclude_saved:
        # Get all saved articles for the user
        saved_articles = PersonalCopy.all_for(user)

        # Exclude both the PersonalCopy article IDs and their parent article IDs
        for article in saved_articles:
            # Add the PersonalCopy article ID
            articles_to_exclude.append(article.id)

            # If this is a simplified version, also exclude the original article
            if article.parent_article_id:
                articles_to_exclude.append(article.parent_article_id)

    # Always exclude hidden articles from recommendations
    hidden_user_articles = (
        UserArticle.query.filter_by(user=user)
        .filter(UserArticle.hidden.isnot(None))
        .all()
    )
    hidden_article_ids = [ua.article_id for ua in hidden_user_articles]
    articles_to_exclude.extend(hidden_article_ids)

    # Exclude articles that the user has reported as broken
    user_reported_articles = UserArticleBrokenReport.query.filter_by(
        user_id=user.id
    ).all()
    reported_article_ids = [report.article_id for report in user_reported_articles]
    articles_to_exclude.extend(reported_article_ids)

    # Remove duplicates from the exclusion list
    articles_to_exclude = list(set(articles_to_exclude))

    try:
        content = article_recommendations_for_user(
            user, count, page, articles_to_exclude
        )
        print("Total content found: ", len(content))
    except Exception as e:
        # Elasticsearch failed, fall back to database query
        print(f"Elasticsearch unavailable, using DB fallback: {type(e).__name__}")
        query = Article.query.filter_by(broken=0).filter_by(
            language_id=user.learned_language_id
        )

        # Apply exclusions to the fallback query as well
        if articles_to_exclude:
            query = query.filter(Article.id.notin_(articles_to_exclude))

        content = query.order_by(Article.published_time.desc()).limit(20).all()

    content_infos = get_user_info_from_content_recommendations(user, content)
    return json_result(content_infos)


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

    article_infos = [
        UserArticle.user_article_info(
            user, UserArticle.select_appropriate_article_for_user(user, e)
        )
        for e in saves
    ]

    return json_result(article_infos)


@cross_domain
@requires_session
def saved_articles():
    user = User.find_by_id(flask.g.user_id)
    saves = PersonalCopy.all_for(user)

    article_infos = [
        UserArticle.user_article_info(
            user, UserArticle.select_appropriate_article_for_user(user, e)
        )
        for e in saves
    ]

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

    # Filter out hidden articles
    filtered_articles = UserArticle.filter_hidden_articles(user, articles)

    article_infos = [
        UserArticle.user_article_info(
            user, UserArticle.select_appropriate_article_for_user(user, a)
        )
        for a in filtered_articles
    ]

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

    # Filter out hidden articles
    filtered_articles = UserArticle.filter_hidden_articles(user, articles)

    article_infos = [
        UserArticle.user_article_info(
            user, UserArticle.select_appropriate_article_for_user(user, a)
        )
        for a in filtered_articles
    ]

    return json_result(article_infos)
