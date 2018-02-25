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
@api.route("/get_user_article_info", methods=("POST",))
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
