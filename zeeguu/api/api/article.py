import flask
import zeeguu.core
from flask import request
from zeeguu.core.model import Article
from zeeguu.api.api.utils.json_result import json_result
from zeeguu.core.model.personal_copy import PersonalCopy

from .utils.route_wrappers import cross_domain, with_session
from . import api, db_session


# ---------------------------------------------------------------------------
@api.route("/find_or_create_article", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def find_or_create_article():
    """

        returns the article at that URL or creates an article and returns it
        - url of the article: str
        - htmlContent: str
        - title: str

    :return: article id as json (e.g. {article_id: 123})

    """

    url = request.form.get("url", "")
    htmlContent = request.form.get("htmlContent", "")
    title = request.form.get("title", "")
    authors = request.form.get("authors", "")

    if not url:
        flask.abort(400)

    try:
        article = Article.find_or_create(
            db_session, url, htmlContent=htmlContent, title=title, authors=authors
        )
        return json_result(article.article_info())
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        print(e)
        flask.abort(500)


# ---------------------------------------------------------------------------
@api.route("/make_personal_copy", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def make_personal_copy():

    article_id = request.form.get("article_id", "")
    article = Article.find_by_id(article_id)
    user = flask.g.user

    if not PersonalCopy.exists_for(user, article):
        PersonalCopy.make_for(user, article, db_session)

    return "OK" if PersonalCopy.exists_for(user, article) else "Something went wrong!"
