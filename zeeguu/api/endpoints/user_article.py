import flask
from flask import request
from zeeguu.core.model import Article, UserArticle, User
from zeeguu.core.model.article_difficulty_feedback import ArticleDifficultyFeedback

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from . import api, db_session

from datetime import datetime

import newspaper


# ---------------------------------------------------------------------------
@api.route("/user_article", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
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


    :return: json as prepared by content_recommender.mysql_recommender.user_article_info

    """

    article_id = request.args.get("article_id", "")
    if not article_id:
        flask.abort(400)

    article_id = int(article_id)

    print(article_id)
    article = Article.query.filter_by(id=article_id).one()
    user = User.find_by_id(flask.g.user_id)
    return json_result(UserArticle.user_article_info(user, article, with_content=True))


# ---------------------------------------------------------------------------
@api.route("/user_article_summary", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_article_summary():
    """
    DEPRECATED: This endpoint is now redundant. The /user_articles/recommended endpoint
    includes tokenized summary/title data directly (via the interactiveSummary and
    interactiveTitle fields).

    This endpoint is maintained for backwards compatibility with forks/extensions.

    Returns tokenized summary (and optionally title) for an article with user bookmarks.
    Much lighter than user_article as it doesn't tokenize the full content.

    :param article_id: article identifier
    :return: json with tokenized summary/title and user bookmarks
    """
    from zeeguu.logging import log

    article_id = request.args.get("article_id", "")
    if not article_id:
        flask.abort(400)

    article_id = int(article_id)

    # Log deprecation warning (but not too frequently to avoid log spam)
    import random
    if random.random() < 0.1:  # Log ~10% of calls
        log(f"[DEPRECATION] /user_article_summary called for article {article_id}. "
            "This endpoint is deprecated - use /user_articles/recommended which includes summary data.")

    article = Article.query.filter_by(id=article_id).one()
    user = User.find_by_id(flask.g.user_id)

    return json_result(UserArticle.user_article_summary_info(user, article))


# ---------------------------------------------------------------------------
@api.route("/article_difficulty_feedback", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def post_article_difficulty_feedback():
    """

    difficulty is expected to be: 1 (too easy), 3 (ok), 5 (too hard)

    """

    article_id = int(request.form.get("article_id"))
    article = Article.query.filter_by(id=article_id).one()

    feedback = request.form.get("difficulty")
    user = User.find_by_id(flask.g.user_id)
    df = ArticleDifficultyFeedback.find_or_create(
        db_session, user, article, datetime.now(), feedback
    )
    db_session.add(df)
    db_session.commit()
    return "OK"


# ---------------------------------------------------------------------------
@api.route("/article_opened", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def article_opened():
    """

    track the fact that the article has been opened by the user


    """

    article_id = int(request.form.get("article_id"))
    article = Article.query.filter_by(id=article_id).one()
    user = User.find_by_id(flask.g.user_id)
    ua = UserArticle.find_or_create(db_session, user, article)
    ua.set_opened()

    db_session.add(ua)
    db_session.commit()

    return "OK"


# ---------------------------------------------------------------------------
@api.route("/user_article", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_article_update():
    """

        update info about this (user x article) pair
        in the form data you can provide
        - liked=True|1|False|0
        - starred -ibidem-

    :return: json as prepared by content_recommender.mysql_recommender.user_article_info

    """

    article_id = int(request.form.get("article_id"))
    starred = request.form.get("starred")
    liked = request.form.get("liked")

    article = Article.query.filter_by(id=article_id).one()
    user = User.find_by_id(flask.g.user_id)
    user_article = UserArticle.find_or_create(db_session, user, article)

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
@requires_session
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
            "language_code": art.meta_lang,
        }
    )


# ---------------------------------------------------------------------------
@api.route("/parse_url", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def parse_url():
    url = request.form.get("url")

    from zeeguu.core.content_retriever import download_and_parse

    parsed = download_and_parse(url)

    return json_result(
        {
            "title": parsed.title,
            "text": parsed.text,
            "htmlContent": parsed.htmlContent,
            "top_image": parsed.top_image,
            "language_code": parsed.meta_lang,
        }
    )


# ---------------------------------------------------------------------------
@api.route("/hide_article", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def hide_article():
    """
    Hide an article from the user's feed.
    When hiding an article, both the original and all simplified versions are hidden.
    When unhiding, both the original and all simplified versions are unhidden.
    
    :param article_id: The ID of the article to hide (can be original or simplified)
    :param hidden: true/false - whether to hide or unhide the article
    :return: "OK" on success
    """
    
    article_id = int(request.form.get("article_id"))
    hidden = request.form.get("hidden", "true")
    hidden_state = hidden in ["true", "True", "1"]
    
    article = Article.query.filter_by(id=article_id).one()
    user = User.find_by_id(flask.g.user_id)
    
    # Determine the parent article (if this is a simplified version)
    # and get all related articles to hide/unhide
    articles_to_update = []
    
    if article.parent_article_id:
        # This is a simplified article - get the parent
        parent_article = article.parent_article
        articles_to_update.append(parent_article)
        # Add all simplified versions
        articles_to_update.extend(parent_article.simplified_versions)
    else:
        # This is the parent article
        articles_to_update.append(article)
        # Add all its simplified versions
        articles_to_update.extend(article.simplified_versions)
    
    # Update hidden state for all related articles
    for art in articles_to_update:
        user_article = UserArticle.find_or_create(db_session, user, art)
        user_article.set_hidden(hidden_state)
        db_session.add(user_article)
    
    db_session.commit()
    
    return "OK"
