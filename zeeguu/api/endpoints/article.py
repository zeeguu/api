import flask
from flask import request
from zeeguu.core.model import Article, Language, User, Topic, UserArticle
from zeeguu.core.model.article_topic_user_feedback import ArticleTopicUserFeedback
from zeeguu.api.utils.json_result import json_result
from zeeguu.core.model.personal_copy import PersonalCopy
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api, db_session
from zeeguu.core.model.article import HTML_TAG_CLEANR

import re
from langdetect import detect
import json
from zeeguu.logging import log


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

    :return: YES|NO: str (for backward compatibility)
            or JSON with detected language info

    """

    htmlContent = request.form.get("htmlContent", "")
    return_detailed = request.form.get("detailed", "false").lower() == "true"

    text = re.sub(HTML_TAG_CLEANR, "", htmlContent)
    try:
        lang = detect(text)

        if return_detailed:
            # Return detailed info for new translation feature
            user = User.find_by_id(flask.g.user_id)
            learned_language = (
                user.learned_language.code if user.learned_language else None
            )

            return json_result(
                {
                    "supported": lang
                    in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED,
                    "detected_language": lang,
                    "learned_language": learned_language,
                    "needs_translation": lang != learned_language
                    and lang in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED,
                }
            )
        else:
            # Backward compatibility
            if lang in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED:
                return "YES"
            else:
                return "NO"
    except:
        if return_detailed:
            return json_result(
                {
                    "supported": False,
                    "detected_language": None,
                    "learned_language": None,
                    "needs_translation": False,
                }
            )
        else:
            return "NO"


# ---------------------------------------------------------------------------
@api.route("/translate_and_adapt_article", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def translate_and_adapt_article():
    """
    Translate an article to the user's learned language and adapt it to their level.

    Expects:
        - url: str - URL of the article to translate
        - target_language: str (optional) - defaults to user's learned language

    Returns:
        JSON with translated article data and fragments
    """
    from zeeguu.core.llm_services.simplification_service import SimplificationService
    from zeeguu.core.model import User
    from zeeguu.core.model.article import Article
    from zeeguu.core.content_retriever import download_and_parse

    url = request.form.get("url")
    if not url:
        flask.abort(400, "URL required")

    user = User.find_by_id(flask.g.user_id)
    target_language = request.form.get("target_language", user.learned_language.code)

    # Get user's CEFR level first for the translated URL key
    try:
        user_level = user.cefr_level_for_learned_language()
        log(f"User {user.id} CEFR level for {target_language}: {user_level}")
    except Exception as e:
        log(f"Error getting CEFR level for user {user.id}: {e}")
        user_level = "A1"  # Default to A1 if there's an error
        log(f"Defaulting to A1 level")

    # Detect source language first
    try:
        article_obj = download_and_parse(url)
        article_content = article_obj.text
        text = re.sub(HTML_TAG_CLEANR, "", article_content)
        source_language = detect(text)
    except Exception as e:
        log(f"Failed to detect source language: {e}")
        source_language = "unknown"

    # Create a unique identifier for this translated article
    # Based on source language, target language and CEFR level so translations can be shared between users
    # Format: url#translated-from-SOURCE-to-TARGET-LEVEL
    translated_url_key = (
        f"{url}#translated-from-{source_language}-to-{target_language}-{user_level}"
    )

    from zeeguu.core.model.url import Url

    # Check if we already have a translated version for this user
    #
    try:
        existing_url = Url.find(translated_url_key)
        if existing_url:
            existing_article = Article.find(translated_url_key)
            if existing_article:
                log(f"Found existing translated article for {url}")
                from zeeguu.core.model.user_article import UserArticle

                uai = UserArticle.user_article_info(
                    user, existing_article, with_content=True
                )
                uai["is_translated"] = True
                # Extract source language from the URL key format: url#translated-from-SOURCE-to-TARGET-LEVEL
                try:
                    # Parse the URL fragment to get source language
                    fragment = translated_url_key.split("#")[
                        1
                    ]  # Get "translated-from-SOURCE-to-TARGET-LEVEL"
                    parts = fragment.split("-")
                    # Format is: translated-from-SOURCE-to-TARGET-LEVEL
                    # So source language is at index 2
                    source_lang = parts[2] if len(parts) > 2 else "unknown"
                    uai["source_language"] = source_lang
                except:
                    uai["source_language"] = "unknown"  # Fallback if parsing fails
                return json_result(uai)
    except:
        # No existing translation found, continue with creating a new one
        pass

    # Fetch the article content using readability server
    try:
        # We already downloaded the article above, reuse it
        article_title = article_obj.title

        log(f"Article content length: {len(article_content)} characters")
        log(f"Article title: {article_title}")
        log(f"First 200 chars: {article_content[:200]}...")

        if not article_content or article_content.strip() == "":
            flask.abort(400, "Could not extract article content from URL")

        # Use the simplification service to translate and adapt
        simplification_service = SimplificationService()

        # Create a combined prompt for translation and adaptation
        result = simplification_service.translate_and_adapt(
            title=article_title,
            content=article_content,
            source_language=source_language,
            target_language=target_language,
            target_level=user_level,
        )

        if not result:
            flask.abort(500, "Translation failed")

        # Create and save the translated article to DB for caching
        from zeeguu.core.model.user_article import UserArticle
        from zeeguu.core.model.source import Source
        from zeeguu.core.model.source_type import SourceType
        from datetime import datetime

        # Create URL and language objects with unique translated URL
        translated_url = Url.find_or_create(db_session, translated_url_key)
        target_lang_obj = Language.find(target_language)

        # Create Source object just like find_or_create does
        source_type = SourceType.find_by_type(SourceType.ARTICLE)
        source = Source.find_or_create(
            db_session,
            result["content"],  # Use translated content
            source_type,
            target_lang_obj,
            0,
        )

        # Use LLM-generated summary if available, otherwise create from content
        if "summary" in result and result["summary"]:
            clean_summary = result["summary"]
        else:
            # Fallback: create summary from content
            from bs4 import BeautifulSoup

            clean_content = BeautifulSoup(result["content"], "html.parser").get_text()
            clean_summary = (
                clean_content[:200] + "..."
                if len(clean_content) > 200
                else clean_content
            )

        # Create article with proper source (like find_or_create does)
        article = Article(
            translated_url,  # url (unique for translation)
            result["title"],  # title
            None,  # authors
            source,  # source (this is the key!)
            result.get("summary", clean_summary),  # summary (clean text)
            datetime.now(),  # published_time
            None,  # feed
            target_lang_obj,  # language
            result["content"],  # htmlContent (keep HTML for parsing)
            None,  # uploader
        )

        # Set the CEFR level to match the user's level for display
        article.cefr_level = user_level

        # Extract and save main image from original article
        from zeeguu.core.content_retriever.article_downloader import (
            extract_article_image,
        )

        main_img_url = extract_article_image(article_obj)
        if main_img_url and main_img_url != "":
            article.img_url = Url.find_or_create(db_session, main_img_url)

        # Save to DB for caching
        db_session.add(article)
        db_session.commit()  # Need to commit to get article.id for fragments

        # Create article fragments (this is what was missing!)
        article.create_article_fragments(db_session)
        db_session.commit()

        # Use the same user_article_info flow as find_or_create_article
        uai = UserArticle.user_article_info(user, article, with_content=True)

        # Mark it as translated
        uai["is_translated"] = True
        uai["source_language"] = source_language

        # Return in the format expected by frontend (like find_or_create_article)
        return json_result(uai)

    except Exception as e:
        log(f"Translation failed for {url}: {str(e)}")
        flask.abort(500, f"Translation failed: {str(e)}")


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
