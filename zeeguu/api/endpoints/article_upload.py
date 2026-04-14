"""
Endpoints for ArticleUpload — the lightweight per-user ingestion entity.

The Chrome extension scrapes the page body, POSTs it here to create an
ArticleUpload, then navigates to /shared-article?upload_id=<id>. The
SharedArticleHandler fetches upload info and shows the choice modal.
On the user's choice, one of the derivation endpoints below runs:
the upload's content becomes a full Article (promoted / simplified /
translated-and-adapted), PersonalCopy is created, and the client
navigates to the reader.

See docs/future-work/extension-ingestion-unification.md
"""
import flask
from flask import request

from zeeguu.core.model import Article, ArticleUpload, User
from zeeguu.core.model.personal_copy import PersonalCopy
from zeeguu.core.model.user_article import UserArticle
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session

from . import api, db_session


def _find_upload_or_404(upload_id, user):
    upload = ArticleUpload.find_by_id(upload_id)
    if not upload:
        flask.abort(404, "Upload not found")
    if upload.user_id != user.id:
        flask.abort(403, "Upload belongs to another user")
    return upload


def _promote_upload(upload):
    """
    Promote an upload's raw content into a full Article row, setting
    source_upload_id as the back-reference. Reuses Article.find_or_create
    so all existing work (fragments, FK, topics, CEFR) happens exactly once.
    """
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


def _ensure_personal_copy(user, article):
    if not PersonalCopy.exists_for(user, article):
        PersonalCopy.make_for(user, article, db_session)


@api.route("/article_upload/create", methods=["POST"])
@cross_domain
@requires_session
def article_upload_create():
    """
    Create a new ArticleUpload from client-scraped content.

    Expects (form):
      - url (required)
      - raw_html (optional but typical for extension)
      - text_content (optional; extension usually sends this too)
      - title, image_url, author (optional)

    Returns: { upload_id, url, title, language, image_url, author, created_at }
    """
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

    upload = ArticleUpload.create(
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
    """Return upload info for the SharedArticleHandler choice modal."""
    user = User.find_by_id(flask.g.user_id)
    upload = _find_upload_or_404(upload_id, user)
    return json_result(upload.as_dictionary())


@api.route("/article_upload/<int:upload_id>/promote_to_article", methods=["POST"])
@cross_domain
@requires_session
def article_upload_promote(upload_id):
    """
    Read Original / Read As-Is: promote the upload to a full Article and
    add a PersonalCopy for the user. Returns user_article_info so the
    client can navigate directly to the reader.
    """
    user = User.find_by_id(flask.g.user_id)
    upload = _find_upload_or_404(upload_id, user)

    article = _promote_upload(upload)
    if not article.cefr_assessment or not article.cefr_assessment.llm_cefr_level:
        article.assess_cefr_level(db_session)

    _ensure_personal_copy(user, article)

    return json_result(UserArticle.user_article_info(user, article, with_content=True))


@api.route("/article_upload/<int:upload_id>/simplify", methods=["POST"])
@cross_domain
@requires_session
def article_upload_simplify(upload_id):
    """
    Promote the upload (so simplification has a parent Article to anchor to)
    and create a simplified version at the user's CEFR level. Returns
    user_article_info for the simplified article.
    """
    from zeeguu.core.llm_services.simplification_and_classification import (
        create_user_specific_simplified_version,
    )

    user = User.find_by_id(flask.g.user_id)
    upload = _find_upload_or_404(upload_id, user)

    parent = _promote_upload(upload)
    if not parent.cefr_assessment or not parent.cefr_assessment.llm_cefr_level:
        parent.assess_cefr_level(db_session)

    try:
        user_level = user.cefr_level_for_learned_language()
    except Exception:
        user_level = "A2"

    existing = [v for v in parent.simplified_versions if v.cefr_level == user_level]
    simplified = existing[0] if existing else create_user_specific_simplified_version(
        db_session, parent, user_level
    )

    target_article = simplified or parent
    _ensure_personal_copy(user, target_article)

    return json_result(
        UserArticle.user_article_info(user, target_article, with_content=True)
    )


@api.route("/article_upload/<int:upload_id>/translate_and_adapt", methods=["POST"])
@cross_domain
@requires_session
def article_upload_translate_and_adapt(upload_id):
    """
    Promote the upload, then delegate to the existing translate-and-adapt
    flow by URL. The existing endpoint caches by URL anyway, so running it
    on the already-promoted article's URL gives us the same behavior as the
    share-sheet path.
    """
    from zeeguu.core.llm_services.simplification_service import SimplificationService
    from zeeguu.core.model import Language
    from zeeguu.core.model.url import Url
    from zeeguu.core.model.source import Source
    from zeeguu.core.model.source_type import SourceType
    from datetime import datetime

    user = User.find_by_id(flask.g.user_id)
    upload = _find_upload_or_404(upload_id, user)

    parent = _promote_upload(upload)
    if not parent.cefr_assessment or not parent.cefr_assessment.llm_cefr_level:
        parent.assess_cefr_level(db_session)

    try:
        user_level = user.cefr_level_for_learned_language()
    except Exception:
        user_level = "A1"

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
    if parent.img_url:
        translated_article.img_url = parent.img_url

    db_session.add(translated_article)
    db_session.commit()

    translated_article.create_article_fragments(db_session)
    db_session.commit()

    _ensure_personal_copy(user, translated_article)

    uai = UserArticle.user_article_info(user, translated_article, with_content=True)
    uai["is_translated"] = True
    uai["source_language"] = source_language
    return json_result(uai)
