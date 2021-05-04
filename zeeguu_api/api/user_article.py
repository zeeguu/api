import flask
from flask import request
from zeeguu_core.model import Article, UserArticle

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api, db_session

import newspaper


# ---------------------------------------------------------------------------
@api.route("/user_article", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def user_article():
    """

        called user_article because it returns info about the article
        but also the user-specific data relative to the article

        takes url as URL argument
        NOTE: the url should be encoded with quote_plus (Pyton) and encodeURIComponent(Javascript)

        this is not perfectly RESTful, but we're not fundamentalist...
        and currently we want to have the url as the URI for the article
        and for some reason if we put the uri as part of the path,
        apache decodes it before we get it in here.
        so for now, we're just not putting it as part of the path


    :return: json as prepared by content_recommender.mixed_recommender.user_article_info

    """

    article_id = request.args.get("article_id", "")
    if not article_id:
        flask.abort(400)

    article_id = int(article_id)

    article = Article.query.filter_by(id=article_id).one()

    return json_result(
        UserArticle.user_article_info(flask.g.user, article, with_content=True)
    )


# ---------------------------------------------------------------------------
@api.route("/article_opened", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def article_opened():
    """

    track the fact that the article has been opened by the user


    """

    article_id = int(request.form.get("article_id"))
    article = Article.query.filter_by(id=article_id).one()
    ua = UserArticle.find_or_create(db_session, flask.g.user, article)
    ua.set_opened()

    db_session.add(ua)
    db_session.commit()

    return "OK"


# ---------------------------------------------------------------------------
@api.route("/user_article", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def user_article_update():
    """

        update info about this (user x article) pair
        in the form data you can provide
        - liked=True|1|False|0
        - starred -ibidem-

    :return: json as prepared by content_recommender.mixed_recommender.user_article_info

    """

    article_id = int(request.form.get("article_id"))
    starred = request.form.get("starred")
    liked = request.form.get("liked")

    article = Article.query.filter_by(id=article_id).one()

    user_article = UserArticle.find_or_create(db_session, flask.g.user, article)

    if starred is not None:
        user_article.set_starred(starred in ["true", "True", "1"])

    if liked is not None:
        user_article.set_liked(liked in ["true", "True", "1"])

    db_session.commit()

    return "OK"


# ---------------------------------------------------------------------------
@api.route("/parse_html", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def parse_html():

    article_html = request.form.get("html")

    art = newspaper.Article(url="")
    art.set_html(article_html)
    art.parse()

    return json_result(
        {
            "title": art.title,
            "text": art.text,
            "top_image": art.top_image,
        }
    )


# ---------------------------------------------------------------------------
@api.route("/parse_url", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def parse_url():

    article_url = request.form.get("url")

    art = newspaper.Article(url=article_url)
    art.download()
    art.parse()

    return json_result(
        {
            "title": art.title,
            "text": art.text,
            "top_image": art.top_image,
        }
    )
