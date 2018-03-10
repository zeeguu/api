import flask
import zeeguu
from flask import request
from zeeguu.content_recommender.mixed_recommender import user_article_info
from zeeguu.model import Article

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

        info about this article in the context of the logged in user

        besides the session, it expects:
        - with_content, optional, because there are times when we don't want the content

    :return: json as prepared by content_recommender.mixed_recommender.user_article_info

    """

    article = Article.find_or_create(session, url)
    return json_result(user_article_info(flask.g.user, article, with_content=True))


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
