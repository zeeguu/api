"""
API endpoints for computing CEFR assessments for articles.

Used by teachers in the article editor to get assessments without saving to DB:
- ML assessment: Fast, auto-recomputes as user types
- LLM assessment: Slow, only on button click
- Effective level: max(LLM, ML) - conservative approach
"""

from flask import request
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from zeeguu.core.model import Article
from zeeguu.logging import log
from . import api


def compute_ml_assessment(content, language_code, fk_difficulty=None, word_count=None):
    """
    Compute ML assessment for given content.

    Returns: (assessment_level, method) tuple or (None, None)
    """
    from zeeguu.core.language.ml_cefr_classifier import predict_cefr_level

    try:
        # Compute FK difficulty and word count if not provided
        if fk_difficulty is None or word_count is None:
            from zeeguu.core.util.compute_fk_word_count import compute_fk_and_wordcount
            from zeeguu.core.model.language import Language

            language = Language.find_or_create(language_code)
            computed_fk, computed_wc = compute_fk_and_wordcount(content, language)

            if fk_difficulty is None:
                fk_difficulty = computed_fk
            if word_count is None:
                word_count = computed_wc

        ml_assessment = predict_cefr_level(
            content, language_code, fk_difficulty, word_count
        )

        # Return None if model prediction failed (e.g., model not available for language)
        if ml_assessment is None:
            return None, None

        return ml_assessment, "ml"

    except Exception as e:
        log(f"Error computing ML assessment: {e}")
        return None, None


def get_max_level(level1, level2):
    """
    Return the harder (higher) of two CEFR levels.
    Conservative approach: if either system thinks it's harder, trust that.
    """
    if not level1:
        return level2
    if not level2:
        return level1

    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    try:
        idx1 = levels.index(level1)
        idx2 = levels.index(level2)
        return level1 if idx1 > idx2 else level2
    except ValueError:
        return level1  # Fallback


@api.route("/article/<int:article_id>/assess_ml", methods=["POST"])
@cross_domain
@requires_session
def assess_ml(article_id):
    """
    Compute ML assessment only (fast, for auto-recompute as user types).

    Expects JSON body:
    {
        "content": "Article text content"
    }

    Returns:
    {
        "ml_assessment": "B1",
        "ml_method": "ml"
    }
    """
    article = Article.find_by_id(article_id)
    if not article:
        return json_result({"error": "Article not found"}), 404

    data = request.get_json()
    content = data.get("content")

    if not content:
        return json_result({"error": "Content is required"}), 400

    ml_assessment, ml_method = compute_ml_assessment(content, article.language.code)

    log(f"ML assessment for article {article_id}: {ml_assessment} ({ml_method})")

    return json_result(
        {
            "ml_assessment": ml_assessment,
            "ml_method": ml_method,
        }
    )


@api.route("/article/<int:article_id>/assess_llm", methods=["POST"])
@cross_domain
@requires_session
def assess_llm(article_id):
    """
    Compute LLM assessment only (slow, for button click).

    Expects JSON body:
    {
        "title": "Article title",
        "content": "Article text content"
    }

    Returns:
    {
        "llm_assessment": "B1",
        "llm_method": "llm_assessed_deepseek"
    }
    """
    article = Article.find_by_id(article_id)
    if not article:
        return json_result({"error": "Article not found"}), 404

    data = request.get_json()
    title = data.get("title", article.title)
    content = data.get("content")

    if not content:
        return json_result({"error": "Content is required"}), 400

    # Compute LLM assessment
    llm_assessment = None
    llm_method = None
    try:
        from zeeguu.core.llm_services.simplification_and_classification import (
            assess_article_cefr_level,
        )

        llm_assessment, llm_method = assess_article_cefr_level(
            title, content, article.language.code
        )
        if llm_assessment:
            log(
                f"LLM assessment for article {article_id}: {llm_assessment} (method: {llm_method})"
            )

    except Exception as e:
        log(f"Error computing LLM assessment for article {article_id}: {e}")
        return json_result({"error": str(e)}), 500

    return json_result(
        {
            "llm_assessment": llm_assessment,
            "llm_method": llm_method,
        }
    )


@api.route("/article/<int:article_id>/initial_assessments", methods=["GET"])
@cross_domain
@requires_session
def initial_assessments(article_id):
    """
    Get initial assessments for article editor.

    Returns parent article's LLM assessment + fresh ML assessment.

    Returns:
    {
        "llm_assessment": "B1",  // from parent if unchanged
        "ml_assessment": "A2",   // freshly computed
        "effective_level": "B1", // max(LLM, ML)
        "teacher_override": null // if teacher has set manual level
    }
    """
    article = Article.find_by_id(article_id)
    if not article:
        return json_result({"error": "Article not found"}), 404

    # Get LLM assessment from article (or parent if this is a copy)
    llm_assessment = article.cefr_level

    # Compute fresh ML assessment
    ml_assessment, ml_method = compute_ml_assessment(
        article.get_content(), article.language.code
    )

    # Calculate effective level (conservative: max of LLM and ML)
    effective_level = get_max_level(llm_assessment, ml_assessment)

    # Check for teacher override
    teacher_override = None
    if article.cefr_assessment:
        teacher_override = article.cefr_assessment.teacher_cefr_level

    return json_result(
        {
            "llm_assessment": llm_assessment,
            "ml_assessment": ml_assessment,
            "effective_level": teacher_override or effective_level,
            "teacher_override": teacher_override,
        }
    )
