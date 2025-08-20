import flask
from flask import request
from zeeguu.core.model import Article, Language, User, Topic, UserArticle
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
        article = Article.find_or_create(db_session, url, do_llm_assessment=True)
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


# ---------------------------------------------------------------------------
@api.route("/simplify_article/<article_id>", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def simplify_article(article_id):
    """
    User-triggered article simplification.
    Creates a simplified version at the user's CEFR level.

    Returns:
        JSON with status and available levels
    """

    article = Article.find_by_id(article_id)
    if not article:
        flask.abort(404, "Article not found")

    # Get the current user's CEFR level
    from zeeguu.core.model import User

    user = User.find_by_id(flask.g.user_id)
    try:
        user_level = user.cefr_level_for_learned_language()
    except:
        user_level = "A2"  # Default to A2 if not set or error

    # Check if already simplified (check for user's specific level)
    existing_simplified = [
        v for v in article.simplified_versions if v.cefr_level == user_level
    ]
    if existing_simplified:
        # Return all existing levels (original + simplified)
        all_levels = []
        # Add original
        from zeeguu.core.language.fk_to_cefr import fk_to_cefr

        original_cefr = article.cefr_level or fk_to_cefr(article.get_fk_difficulty())
        all_levels.append(
            {"id": article.id, "cefr_level": original_cefr, "is_original": True}
        )
        # Add simplified versions
        for v in article.simplified_versions:
            all_levels.append(
                {"id": v.id, "cefr_level": v.cefr_level, "is_original": False}
            )
        return json_result({"status": "already_done", "levels": all_levels})

    # Simplify now (user is waiting) - only create user's level
    try:
        from zeeguu.core.llm_services.article_simplification import (
            create_user_specific_simplified_version,
        )

        simplified_article = create_user_specific_simplified_version(
            db_session, article, user_level
        )

        if simplified_article:
            # Return all available levels (original + new simplified)
            all_levels = []
            # Add original
            from zeeguu.core.language.fk_to_cefr import fk_to_cefr

            original_cefr = article.cefr_level or fk_to_cefr(
                article.get_fk_difficulty()
            )
            all_levels.append(
                {"id": article.id, "cefr_level": original_cefr, "is_original": True}
            )
            # Add all simplified versions (including the new one)
            for v in article.simplified_versions:
                all_levels.append(
                    {"id": v.id, "cefr_level": v.cefr_level, "is_original": False}
                )

            return json_result({"status": "success", "levels": all_levels})
        else:
            return json_result(
                {"status": "error", "message": "Failed to create simplified version"}
            )

    except Exception as e:
        from zeeguu.logging import log

        log(f"Simplification failed for article {article_id}: {str(e)}")
        return json_result({"status": "failed", "error": str(e)[:200]})


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
