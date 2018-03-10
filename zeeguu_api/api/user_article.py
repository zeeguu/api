import flask
import zeeguu
from flask import request
from zeeguu.content_recommender.mixed_recommender import user_article_info, article_recommendations_for_user
from zeeguu.model import Article, UserArticle

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api

session = zeeguu.db.session


# ---------------------------------------------------------------------------
@api.route("/user_article/<path:url>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def user_article(url):
    """

        called user_article because it returns info about the article
        but also the user-specific data relative to the article

    :return: json as prepared by content_recommender.mixed_recommender.user_article_info

    """

    article = Article.find_or_create(session, url)
    return json_result(user_article_info(flask.g.user, article, with_content=True))


# ---------------------------------------------------------------------------
@api.route("/user_article/<path:url>", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def user_article_update(url):
    """

        update info about this (user x article) pair
        in the post form data can take
        - liked
        - starred

    :return: json as prepared by content_recommender.mixed_recommender.user_article_info

    """

    starred = request.form.get('starred')
    liked = request.form.get('liked')

    article = Article.find_or_create(session, url)
    user_article = UserArticle.find_or_create(session, flask.g.user, article)

    if starred is not None:
        user_article.set_starred(starred in ["True", "1"])

    if liked is not None:
        user_article.set_liked(liked in ["True", "1"])

    session.commit()

    return "OK"


# ---------------------------------------------------------------------------
# !!!!!!!!!!!!!!!!!!!!!!!!! DEPRECATED !!!!!!!!!!!!!!!!!!!!!!!!!
@api.route("/get_user_article_info", methods=("POST",))
# !!!!!!!!!!!!!!!!!!!!!!!!! DEPRECATED !!!!!!!!!!!!!!!!!!!!!!!!!
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_user_article_info():
    """

        expects one parameter: url

    :return: json dictionary with info

    """

    url = str(request.form.get('url', ''))

    article = Article.find_or_create(session, url)

    return json_result(user_article_info(flask.g.user, article))
