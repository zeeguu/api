import flask
from flask import request

import zeeguu

from . import api
from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from zeeguu.model import StarredArticle

session = zeeguu.db.session


@api.route("/star_article", methods=["POST"])
@cross_domain
@with_session
def star_article():
    """

        Will star the article with :param url, :param title and in :param language_id
        All the three parameters are required as post arguments

    """

    url = request.form.get('url', '')
    title = request.form.get('title', '')
    language_id = request.form.get('language_id', '')

    StarredArticle.find_or_create(session, flask.g.user, url, title, language_id)

    return "OK"


@api.route("/unstar_article", methods=["POST"])
@cross_domain
@with_session
def unstar_article():
    """

        Will unstar the article with the given :param url

    """

    url = request.form.get('url', '')

    StarredArticle.delete(session, flask.g.user, url)

    return "OK"


@api.route("/get_starred_articles", methods=["GET"])
@cross_domain
@with_session
def get_starred_articles():
    """

        Returns a list of starred articles.

        Example return:

        [{'user_id': 1, 'url': 'http://mir.lu', 'title': 'test', 'language': 'en', 'starred_date': '2017-06-12T20:17:48'}]

    """

    articles = StarredArticle.all_for_user(flask.g.user)
    list_of_dicts = [each.as_dict() for each in articles]

    return json_result(list_of_dicts)
