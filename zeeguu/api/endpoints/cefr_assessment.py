"""
The teacher's say on the CEFR level of a text they uploaded.

The LLM and ML assessments are written by the crawler and the upload code
directly through ArticleCefrAssessment; the article info sends all of them
to the teacher (Article.article_info_for_teacher, "cefr_assessments").
"""

import flask
from flask import request

from zeeguu.core import cefr
from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import Article, User, ArticleCefrAssessment
from . import api, db_session


def _not_your_text():
    # A level is shared by every reader of the article, so only its uploader
    # sets it. The web client calls this only from the own-text editor.
    return make_error(403, "You can only set the level of texts you uploaded")


@api.route("/article/<article_id>/resolve_cefr", methods=["POST"])
@cross_domain
@requires_session
def resolve_cefr(article_id):
    """
    Teacher resolves a CEFR level disagreement.

    Creates a "teacher_resolution" assessment and updates the effective_cefr_level.

    Request Parameters:
        cefr_level: The CEFR level chosen by the teacher (A1-C2)

    Returns:
        JSON with:
        {
            "status": "success",
            "article_id": 123,
            "resolved_level": "A1",
            "effective_cefr_level": "A1",
            "display_cefr": "A1"  # kept for backward compatibility
        }
    """
    article = Article.find_by_id(article_id)
    if not article:
        flask.abort(404, "Article not found")

    user = User.find_by_id(flask.g.user_id)
    if not article.is_owned_by(user):
        return _not_your_text()

    cefr_level = request.form.get("cefr_level")
    if not cefr_level:
        flask.abort(400, "Missing required parameter: cefr_level")

    # Validate CEFR level
    if not cefr.is_level(cefr_level):
        flask.abort(400, f"Invalid CEFR level. Must be one of: {', '.join(cefr.LEVELS)}")

    # Get or create assessment record (1:1)
    assessment = ArticleCefrAssessment.find_or_create(db_session, article_id, commit=False)
    assessment.set_teacher_assessment(cefr_level, "teacher_resolution", user.id)

    # Update legacy fields for backward compatibility
    article.cefr_level = cefr_level
    article.cefr_source = "teacher_resolution"
    if hasattr(article, 'cefr_assessed_by_user_id'):
        article.cefr_assessed_by_user_id = user.id

    db_session.add(article)
    db_session.add(assessment)
    db_session.commit()

    return json_result({
        "status": "success",
        "article_id": int(article_id),
        "resolved_level": cefr_level,
        "effective_cefr_level": assessment.effective_cefr_level,
        # Keep display_cefr for backward compatibility
        "display_cefr": assessment.effective_cefr_level
    })
