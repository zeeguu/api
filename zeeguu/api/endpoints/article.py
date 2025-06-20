import flask
from flask import request
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.model.topic import Topic
from zeeguu.core.model.user import User
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.article_topic_user_feedback import ArticleTopicUserFeedback
from zeeguu.api.utils import json_result
from zeeguu.core.model.personal_copy import PersonalCopy
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api, db_session
from zeeguu.core.model.article import HTML_TAG_CLEANR

import re
from langdetect import detect
import json


# ---------------------------------------------------------------------------
@api.route("/find_or_create_article", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def find_or_create_article():
    """

        returns the article at that URL or creates an article and returns it
        - url of the article: str

    :return: article id as json (e.g. {article_id: 123})

    """

    url = request.form.get("url", "")
    print("-- url: " + url)
    user = User.find_by_id(flask.g.user_id)
    print("-- user: " + str(user.id))

    if not url:
        print("-- missing url: aborting")
        flask.abort(400)

    try:
        article = Article.find_or_create(db_session, url)
        print("-- article found or created: " + str(article.id))
        uai = UserArticle.user_article_info(user, article, with_content=True)
        print("-- returning user article info: ", json.dumps(uai)[:50])
        return json_result(uai)
    except NoResultFound as e:
        print(f"Exception: '{e}'")
        flask.abort(406, "Language not supported")
    except Exception as e:
        from zeeguu.logging import print_and_log_to_sentry

        print_and_log_to_sentry(e)

        import traceback

        traceback.print_exc()

        flask.abort(500)


# ---------------------------------------------------------------------------
@api.route("/make_personal_copy", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def make_personal_copy():
    article_id = request.form.get("article_id", "")
    article = Article.find_by_id(article_id)
    user = User.find_by_id(flask.g.user_id)

    if not PersonalCopy.exists_for(user, article):
        PersonalCopy.make_for(user, article, db_session)

    return "OK" if PersonalCopy.exists_for(user, article) else "Something went wrong!"


# ---------------------------------------------------------------------------
@api.route("/remove_personal_copy", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def remove_personal_copy():
    article_id = request.form.get("article_id", "")
    article = Article.find_by_id(article_id)
    user = User.find_by_id(flask.g.user_id)

    if PersonalCopy.exists_for(user, article):
        PersonalCopy.remove_for(user, article, db_session)

    return (
        "OK" if not PersonalCopy.exists_for(user, article) else "Something went wrong!"
    )


# ---------------------------------------------------------------------------
@api.route("/is_article_language_supported", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def is_article_language_supported():
    """
    Expects:
        - htmlContent: str

    :return: YES|NO: str

    """

    htmlContent = request.form.get("htmlContent", "")

    text = re.sub(HTML_TAG_CLEANR, "", htmlContent)
    try:
        lang = detect(text)
        if lang in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED:
            return "YES"
        else:
            return "NO"
    except:
        return "NO"


@api.route("/remove_ml_suggestion", methods=["POST"])
@cross_domain
@requires_session
def remove_ml_suggestion():
    """
    Saves a user feedback to remove a ML prediction
    of the new topics. Can indicate that the prediciton
    isn't correct.
    """
    user = User.find_by_id(flask.g.user_id)
    article_id = request.form.get("article_id", "")
    topic = request.form.get("topic", "")
    article = Article.find_by_id(article_id)
    topic = Topic.find(topic)
    try:
        ArticleTopicUserFeedback.find_or_create(
            db_session,
            article,
            user,
            topic,
            ArticleTopicUserFeedback.DO_NOT_SHOW_FEEDBACK,
        )
        return "OK"
    except Exception as e:
        from zeeguu.logging import print_and_log_to_sentry

        print_and_log_to_sentry(e)
        return "Something went wrong!"
