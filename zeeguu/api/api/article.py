import flask
import zeeguu.core
from flask import request
from zeeguu.core.model import Article
from zeeguu.api.api.utils.json_result import json_result

from .utils.route_wrappers import cross_domain, with_session
from . import api, db_session


# ---------------------------------------------------------------------------
@api.route("/find_or_create_article", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def article_id():
    """

        returns the article at that URL or creates an article and returns it
        - url of the article
            NOTE!!!! url is encoded with quote_plus (Pyton) and encodeURIComponent(Javascript)
        - htmlContent: str
        - title: str

    :return: article id as json (e.g. {article_id: 123})

    """

    url = request.form.get("url", "")
    htmlContent = request.form.get("htmlContent", "")
    title = request.form.get("title", "")

    if not url:
        flask.abort(400)

    try:
        article = Article.find_or_create(
            db_session, url, htmlContent=htmlContent, title=title
        )
        return json_result(dict(article_id=article.id))
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        zeeguu.core.log(e)
        flask.abort(500)
