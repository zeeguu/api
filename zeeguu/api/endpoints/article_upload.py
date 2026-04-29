"""Endpoints for ArticleUpload — lightweight per-user ingestion entity."""
import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import Article, ArticleUpload, User
from zeeguu.core.model.personal_copy import PersonalCopy
from zeeguu.core.model.user_article import UserArticle
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session

from . import api, db_session

_DEFAULT_CEFR_LEVEL = "A2"


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
    from zeeguu.core.model.url import Url

    url = request.form.get("url", "").strip()
    if not url:
        flask.abort(400, "url required")

    raw_html = request.form.get("raw_html") or None
    text_content = request.form.get("text_content") or None
    title = request.form.get("title") or None
    image_url = request.form.get("image_url") or None
    author = request.form.get("author") or None

    if not raw_html and not text_content:
        flask.abort(400, "raw_html or text_content required")

    user = User.find_by_id(flask.g.user_id)

    # Short-circuit re-sends of the same URL.
    url_obj = Url.find_or_create(db_session, url, title=title or "")
    existing = ArticleUpload.query.filter_by(user_id=user.id, url_id=url_obj.id).first()
    if existing:
        return json_result(existing.as_dictionary())

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
    from zeeguu.core.language.cefr_estimator import estimate_cefr_for_text

    user = User.find_by_id(flask.g.user_id)
    upload = _find_upload_or_404(upload_id, user)
    payload = upload.as_dictionary()

    # Mirror /detect_article_info: the share-flow modal renders the level
    # when present. Estimation is a few-ms ML+FK pass over a 5KB sample.
    try:
        lang_code = upload.language.code if upload.language else None
        payload["cefr_level"] = estimate_cefr_for_text(
            upload.text_content or upload.raw_html or "", lang_code
        )
    except Exception:
        payload["cefr_level"] = None

    return json_result(payload)


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
