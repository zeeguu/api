import flask
import zeeguu
from zeeguu.content_recommender.mixed_recommender import user_article_info
from zeeguu.model import Article

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api

session = zeeguu.db.session


# ---------------------------------------------------------------------------
@api.route("/get_user_article_info/<_url>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_user_article_info(_url: str):
    """

        Retrieve info about the article at :param _url

    :return: json dictionary with info

    """
    article = Article.find_or_create(session, _url)

    return json_result(user_article_info(flask.g.user, article))
