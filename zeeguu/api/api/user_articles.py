import flask

from zeeguu.core.content_recommender import article_recommendations_for_user
from zeeguu.core.model import UserArticle

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api


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

    articles = article_recommendations_for_user(flask.g.user, count)
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
