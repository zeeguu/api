"""
API endpoints for CEFR assessment management.

Handles multiple assessments per article (LLM, ML, teacher resolution)
and provides display logic for disagreements.
"""

import flask
from flask import request

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import Article, User, ArticleCefrAssessment
from . import api, db_session


@api.route("/article/<article_id>/cefr_assessments", methods=["GET"])
@cross_domain
@requires_session
def get_cefr_assessments(article_id):
    """
    Get all CEFR assessments for an article.

    Returns assessments from the 1:1 assessment table (LLM, ML, Teacher).

    Returns:
        JSON with:
        {
            "article_id": 123,
            "display_cefr": "A1/A2",  # Computed display value
            "llm": {
                "level": "A1",
                "method": "llm_assessed_deepseek",
                "assessed_at": "2025-10-15T10:30:00"
            },
            "ml": {
                "level": "A2",
                "method": "ml",
                "assessed_at": "2025-10-15T10:31:00"
            },
            "teacher": null  # No teacher resolution yet
        }
    """
    article = Article.find_by_id(article_id)
    if not article:
        flask.abort(404, "Article not found")

    # Get assessment record (1:1)
    assessment = article.cefr_assessment

    if not assessment:
        return json_result({
            "article_id": int(article_id),
            "display_cefr": None,
            "llm": None,
            "ml": None,
            "teacher": None
        })

    # Return assessment data as dict
    result = assessment.as_dict()
    result["article_id"] = int(article_id)

    return json_result(result)


@api.route("/article/<article_id>/display_cefr", methods=["GET"])
@cross_domain
@requires_session
def get_display_cefr(article_id):
    """
    Get the effective CEFR level for an article.

    Returns the computed effective level from assessment table.

    Returns:
        JSON with:
        {
            "article_id": 123,
            "effective_cefr_level": "B1/B2",  # or "B1" for single level
            "display_cefr": "B1/B2"  # kept for backward compatibility
        }
    """
    article = Article.find_by_id(article_id)
    if not article:
        flask.abort(404, "Article not found")

    effective_level = None
    if article.cefr_assessment:
        effective_level = article.cefr_assessment.effective_cefr_level

    return json_result({
        "article_id": int(article_id),
        "effective_cefr_level": effective_level,
        # Keep display_cefr for backward compatibility
        "display_cefr": effective_level
    })


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

    cefr_level = request.form.get("cefr_level")
    if not cefr_level:
        flask.abort(400, "Missing required parameter: cefr_level")

    # Validate CEFR level
    valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    if cefr_level not in valid_levels:
        flask.abort(400, f"Invalid CEFR level. Must be one of: {', '.join(valid_levels)}")

    user = User.find_by_id(flask.g.user_id)

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


@api.route("/article/<article_id>/store_cefr_assessment", methods=["POST"])
@cross_domain
@requires_session
def store_cefr_assessment(article_id):
    """
    Store a CEFR assessment for an article.

    Used internally when assessments are performed (LLM during crawling, ML during estimation, etc.)

    Request Parameters:
        cefr_level: CEFR level (A1-C2)
        assessment_method: How it was assessed (llm_assessed_deepseek, ml, ml_word_freq, etc.)

    Returns:
        JSON with:
        {
            "status": "success",
            "article_id": 123,
            "effective_cefr_level": "B1/B2",  # Computed effective level
            "display_cefr": "B1/B2"  # kept for backward compatibility
        }
    """
    article = Article.find_by_id(article_id)
    if not article:
        flask.abort(404, "Article not found")

    cefr_level = request.form.get("cefr_level")
    assessment_method = request.form.get("assessment_method")

    if not cefr_level or not assessment_method:
        flask.abort(400, "Missing required parameters: cefr_level and assessment_method")

    # Validate CEFR level
    valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    if cefr_level not in valid_levels:
        flask.abort(400, f"Invalid CEFR level. Must be one of: {', '.join(valid_levels)}")

    # Validate assessment method
    valid_methods = [
        "llm_assessed_deepseek",
        "llm_assessed_anthropic",
        "ml",
        "ml_word_freq",
        "teacher_resolution",
        "teacher_manual",
        "naive_fk",
        "unknown"
    ]
    if assessment_method not in valid_methods:
        flask.abort(400, f"Invalid assessment method. Must be one of: {', '.join(valid_methods)}")

    # Get or create assessment record (1:1)
    assessment = ArticleCefrAssessment.find_or_create(db_session, article_id, commit=False)

    # Store assessment based on category
    if assessment_method in ["teacher_resolution", "teacher_manual"]:
        user_id = request.form.get("assessed_by_user_id", flask.g.user_id)
        assessment.set_teacher_assessment(cefr_level, assessment_method, user_id)
    elif assessment_method in ["llm_assessed_deepseek", "llm_assessed_anthropic"]:
        assessment.set_llm_assessment(cefr_level, assessment_method)
    elif assessment_method in ["ml", "ml_word_freq", "naive_fk"]:
        assessment.set_ml_assessment(cefr_level, assessment_method)

    # Update legacy fields for backward compatibility
    # For compound levels, store the lower level in legacy field
    if assessment.effective_cefr_level:
        if "/" in assessment.effective_cefr_level:
            # Extract first (lower) level for legacy field
            article.cefr_level = assessment.effective_cefr_level.split("/")[0]
        else:
            article.cefr_level = assessment.effective_cefr_level
        article.cefr_source = assessment_method

    db_session.add(article)
    db_session.add(assessment)
    db_session.commit()

    return json_result({
        "status": "success",
        "article_id": int(article_id),
        "effective_cefr_level": assessment.effective_cefr_level,
        # Keep display_cefr for backward compatibility
        "display_cefr": assessment.effective_cefr_level
    })
