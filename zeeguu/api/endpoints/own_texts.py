import flask
import sqlalchemy
from flask import request

from zeeguu.core.model import Article, Language, CohortArticleMap, UserArticle, User
from zeeguu.core.model.personal_copy import PersonalCopy

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from . import api, db_session


@api.route("/upload_own_text", methods=["POST"])
@cross_domain
@requires_session
def upload_own_text():

    db_session.rollback()
    language = Language.find_or_create(request.form.get("language", ""))
    content = request.form.get("content", "")
    htmlContent = request.form.get("htmlContent", "")
    title = request.form.get("title", "")
    original_cefr_level = request.form.get("original_cefr_level", None)
    img_url = request.form.get("img_url", None)
    user = User.find_by_id(flask.g.user_id)
    new_article_id = Article.create_from_upload(
        db_session, title, content, htmlContent, user, language, original_cefr_level, img_url
    )

    return str(new_article_id)


@api.route("/own_texts", methods=["GET"])
@cross_domain
@requires_session
def own_texts():
    user = User.find_by_id(flask.g.user_id)
    r = Article.own_texts_for_user(user)
    r2 = PersonalCopy.all_for(user)
    all_articles = r + r2
    all_articles.sort(key=lambda art: art.id, reverse=True)

    # For own/saved texts, show exactly what the teacher uploaded or saved
    # Don't apply automatic article selection based on user's CEFR level
    article_infos = [UserArticle.user_article_info(user, e) for e in all_articles]

    return json_result(article_infos)


@api.route("/delete_own_text/<id>", methods=["GET"])
@cross_domain
@requires_session
def delete_own_text(id):

    try:
        a = Article.query.filter(Article.id == id).one()
        user = User.find_by_id(flask.g.user_id)

        was_permanently_deleted = a.safe_delete(db_session, user)

        if was_permanently_deleted:
            return json_result(dict(
                success=True,
                message="Article permanently deleted"
            ))
        else:
            return json_result(dict(
                success=True,
                message="Article hidden from your library. Other users who have read this article can still access it."
            ))

    except sqlalchemy.orm.exc.NoResultFound:
        return json_result(dict(
            success=False,
            message="Article not found"
        ))


@api.route("/update_own_text/<article_id>", methods=["POST"])
@cross_domain
@requires_session
def update_own_text(article_id):

    language = Language.find_or_create(request.form.get("language", ""))
    content = request.form.get("content", "")
    title = request.form.get("title", "")
    htmlContent = request.form.get("htmlContent", "")

    a = Article.query.filter(Article.id == article_id).one()
    a.update(db_session, language, content, htmlContent, title)

    db_session.add(a)
    db_session.commit()

    return "OK"


@api.route("/estimate_article_cefr", methods=["POST"])
@cross_domain
@requires_session
def estimate_article_cefr():
    """
    Estimate CEFR level for article content without requiring an article ID.
    Used when creating new articles before they're saved to the database.

    Returns ML assessment for the given content.
    """
    from zeeguu.api.endpoints.article_cefr_recompute import compute_ml_assessment
    from zeeguu.logging import log

    content = request.form.get("content", "")
    language_code = request.form.get("language", "")
    title = request.form.get("title", "")  # Not used for ML, but kept for API compatibility

    log(f"estimate_article_cefr: received language_code='{language_code}', content length={len(content)}, title='{title}'")

    if not content or not language_code:
        error_msg = f"Missing required fields - content: {len(content)} chars, language: '{language_code}'"
        log(f"estimate_article_cefr: ERROR - {error_msg}")
        return json_result({"error": error_msg}), 400

    ml_assessment, ml_method = compute_ml_assessment(content, language_code)

    log(f"estimate_article_cefr: ML assessment result: level={ml_assessment}, method={ml_method}")

    if ml_assessment is None:
        # Check if model exists for this language
        import os
        data_folder = os.environ.get("ZEEGUU_DATA_FOLDER")
        model_path = None
        if data_folder:
            model_path = os.path.join(
                data_folder,
                "ml_models",
                "cefr_estimation",
                f"cefr_classifier_{language_code}.pkl",
            )

        model_exists = model_path and os.path.exists(model_path)
        error_msg = f"ML model unavailable for language '{language_code}' (model exists: {model_exists}, path: {model_path})"
        log(f"estimate_article_cefr: {error_msg}")

        return json_result({
            "cefr_level": None,
            "assessment_method": None,
            "error": error_msg,
            "debug": {
                "language_code": language_code,
                "model_exists": model_exists,
                "model_path": model_path,
                "data_folder": data_folder
            }
        })

    return json_result({
        "cefr_level": ml_assessment,
        "assessment_method": ml_method
    })
