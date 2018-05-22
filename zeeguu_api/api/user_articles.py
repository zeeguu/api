import flask
import zeeguu
from zeeguu.content_recommender.mixed_recommender import article_recommendations_for_user
from zeeguu.model import UserArticle

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api

session = zeeguu.db.session


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

    return json_result(article_recommendations_for_user(flask.g.user, count))


# ---------------------------------------------------------------------------
@api.route("/user_articles/starred_or_liked", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def user_articles_starred_and_liked():
    return json_result(UserArticle.all_starred_and_liked_articles_of_user_info(flask.g.user))

