import flask
from flask import request

import zeeguu
from zeeguu.model.user_article import UserArticle

from . import api
from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from zeeguu.model import Article

session = zeeguu.db.session


@api.route("/star_article", methods=["POST"])
@cross_domain
@with_session
def star_article():
    """

        Will star the article with :param url

        This used to required also :param title and in :param language_id
        but we're not using them anymore.

    """

    url = str(request.form.get('url', ''))

    article = Article.find(url)
    article.star_for_user(session, flask.g.user)
    session.commit()

    return "OK"


@api.route("/unstar_article", methods=["POST"])
@cross_domain
@with_session
def unstar_article():
    """

        Requires :param url

    """

    url = str(request.form.get('url', ''))

    article = Article.find(url)
    article.star_for_user(session, flask.g.user, False)
    session.commit()

    return "OK"


@api.route("/get_starred_articles", methods=["GET"])
@cross_domain
@with_session
def get_starred_articles():
    """

        Returns a list of starred articles and
        associated info

        Example return:

        [
            {'user_id': 1,
            'url': 'http://mir.lu',
            'title': 'test',
            'language': 'en',
            'starred_date': '2017-06-12T20:17:48'}]

    """

    return json_result(UserArticle.all_starred_articles_of_user_info(flask.g.user))
