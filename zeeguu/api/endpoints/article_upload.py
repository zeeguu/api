"""Endpoints for ArticleUpload — lightweight per-user ingestion entity."""
import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import Article, ArticleUpload, User
from zeeguu.core.model.personal_copy import PersonalCopy
from zeeguu.core.model.user_article import UserArticle
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.logging import log

from . import api, db_session

_DEFAULT_CEFR_LEVEL = "A2"


def _extract_with_readability_server(url, raw_html):
    """
    Run the readability_server on raw_html and return a dict with
    cleaned {title, text, image_url, author, language_code}, or None
    if extraction fails. Never raises; callers fall back to client hints.
    """
    from zeeguu.core.content_retriever import readability_download_and_parse
    from zeeguu.core.content_retriever.article_downloader import extract_article_image

    try:
        np_article = readability_download_and_parse(url, html_content=raw_html)
    except Exception as e:
        log(f"readability_server extraction failed for {url}: {e}")
        return None

    image = extract_article_image(np_article) or None

    return {
        "title": np_article.title or None,
        "text": np_article.text or None,
        "image_url": image,
        "author": ", ".join(np_article.authors) if np_article.authors else None,
        "language_code": np_article.meta_lang or None,
    }


def _find_upload_or_404(upload_id, user):
    upload = ArticleUpload.find_by_id(upload_id)
    if not upload:
        flask.abort(404, "Upload not found")
    if upload.user_id != user.id:
        flask.abort(403, "Upload belongs to another user")
    return upload


def _promote_upload_or_abort(upload):
    from zeeguu.core.content_retriever.crawler_exceptions import (
        FailedToParseWithReadabilityServer,
    )

    try:
        return Article.find_or_create(
            db_session,
            upload.url.as_string(),
            html_content=upload.raw_html,
            text_content=upload.text_content,
            title=upload.title,
            author=upload.author,
            image_url=upload.image_url,
            source_upload_id=upload.id,
        )
    except NoResultFound:
        flask.abort(406, "Language not supported")
    except FailedToParseWithReadabilityServer:
        flask.abort(422, "Could not parse article content")


def _user_cefr_level(user):
    try:
        return user.cefr_level_for_learned_language()
    except Exception:
        return _DEFAULT_CEFR_LEVEL


def _ensure_personal_copy(user, article):
    if not PersonalCopy.exists_for(user, article):
        PersonalCopy.make_for(user, article, db_session)


@api.route("/article_upload/create", methods=["POST"])
@cross_domain
@requires_session
def article_upload_create():
    url = request.form.get("url", "").strip()
    if not url:
        flask.abort(400, "url required")

    raw_html = request.form.get("raw_html") or None
    client_text = request.form.get("text_content") or None
    client_title = request.form.get("title") or None
    client_image = request.form.get("image_url") or None
    client_author = request.form.get("author") or None

    if not raw_html and not client_text:
        flask.abort(400, "raw_html or text_content required")

    # Prefer server-side extraction so uploads match the metadata quality
    # (title, image, summary basis, author, language) the crawler produces.
    # Fall back to client-provided hints if readability_server is unreachable
    # or the page can't be cleanly parsed.
    server_extracted = _extract_with_readability_server(url, raw_html) if raw_html else None
    if server_extracted:
        text_content = server_extracted["text"] or client_text
        title = server_extracted["title"] or client_title
        image_url = server_extracted["image_url"] or client_image
        author = server_extracted["author"] or client_author
    else:
        text_content, title, image_url, author = client_text, client_title, client_image, client_author

    user = User.find_by_id(flask.g.user_id)

    upload = ArticleUpload.find_or_create(
        db_session,
        user=user,
        url_string=url,
        raw_html=raw_html,
        text_content=text_content,
        title=title,
        image_url=image_url,
        author=author,
    )
    return json_result(upload.as_dictionary())


@api.route("/article_upload/<int:upload_id>", methods=["GET"])
@cross_domain
@requires_session
def article_upload_get(upload_id):
    user = User.find_by_id(flask.g.user_id)
    upload = _find_upload_or_404(upload_id, user)
    return json_result(upload.as_dictionary())


@api.route("/article_upload/<int:upload_id>/promote_to_article", methods=["POST"])
@cross_domain
@requires_session
def article_upload_promote(upload_id):
    user = User.find_by_id(flask.g.user_id)
    upload = _find_upload_or_404(upload_id, user)

    article = _promote_upload_or_abort(upload)
    if not article.cefr_assessment or not article.cefr_assessment.llm_cefr_level:
        article.assess_cefr_level(db_session)

    _ensure_personal_copy(user, article)

    return json_result(UserArticle.user_article_info(user, article, with_content=True))


@api.route("/article_upload/<int:upload_id>/simplify", methods=["POST"])
@cross_domain
@requires_session
def article_upload_simplify(upload_id):
    from zeeguu.core.llm_services.simplification_and_classification import (
        create_simplified_version_from_upload,
    )

    user = User.find_by_id(flask.g.user_id)
    upload = _find_upload_or_404(upload_id, user)

    user_level = _user_cefr_level(user)

    existing = Article.query.filter_by(
        source_upload_id=upload.id, cefr_level=user_level
    ).first()
    simplified = existing or create_simplified_version_from_upload(
        db_session, upload, user_level
    )
    if simplified is None:
        flask.abort(500, "Could not simplify this upload")

    _ensure_personal_copy(user, simplified)

    return json_result(
        UserArticle.user_article_info(user, simplified, with_content=True)
    )


@api.route("/article_upload/<int:upload_id>/translate_and_adapt", methods=["POST"])
@cross_domain
@requires_session
def article_upload_translate_and_adapt(upload_id):
    from zeeguu.core.llm_services.simplification_service import SimplificationService
    from zeeguu.core.model import Language
    from zeeguu.core.model.url import Url
    from zeeguu.core.model.source import Source
    from zeeguu.core.model.source_type import SourceType
    from datetime import datetime

    user = User.find_by_id(flask.g.user_id)
    upload = _find_upload_or_404(upload_id, user)

    user_level = _user_cefr_level(user)
    target_language = user.learned_language.code
    source_language = upload.language.code if upload.language else "unknown"

    translated_url_key = (
        f"{upload.url.as_string()}"
        f"#translated-from-{source_language}-to-{target_language}-{user_level}"
    )

    existing_article = Article.find(translated_url_key)
    if existing_article:
        _ensure_personal_copy(user, existing_article)
        uai = UserArticle.user_article_info(user, existing_article, with_content=True)
        uai["is_translated"] = True
        uai["source_language"] = source_language
        return json_result(uai)

    content = upload.text_content or upload.raw_html or ""
    title = upload.title or ""

    service = SimplificationService()
    result = service.translate_and_adapt(
        title=title,
        content=content,
        source_language=source_language,
        target_language=target_language,
        target_level=user_level,
    )
    if not result:
        flask.abort(500, "Translation failed")

    translated_url = Url.find_or_create(db_session, translated_url_key)
    target_lang_obj = Language.find(target_language)
    source_type = SourceType.find_by_type(SourceType.ARTICLE)
    source_obj = Source.find_or_create(
        db_session, result["content"], source_type, target_lang_obj, 0
    )

    clean_summary = result.get("summary") or (result["content"][:200] + "...")

    translated_article = Article(
        translated_url,
        result["title"],
        None,
        source_obj,
        clean_summary,
        datetime.now(),
        None,
        target_lang_obj,
        result["content"],
        None,
    )
    translated_article.cefr_level = user_level
    translated_article.source_upload_id = upload.id
    if upload.image_url:
        translated_article.img_url = Url.find_or_create(db_session, upload.image_url)

    db_session.add(translated_article)
    db_session.commit()

    translated_article.create_article_fragments(db_session)
    db_session.commit()

    _ensure_personal_copy(user, translated_article)

    uai = UserArticle.user_article_info(user, translated_article, with_content=True)
    uai["is_translated"] = True
    uai["source_language"] = source_language
    return json_result(uai)
