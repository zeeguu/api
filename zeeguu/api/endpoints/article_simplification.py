"""
API endpoints for article simplification.
"""

import flask
from flask import request

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import Article
from . import api


def _get_difficulty_label(cefr_level):
    """
    Convert CEFR level to human-readable difficulty label.
    """
    difficulty_map = {
        "A1": "A1 - Beginner",
        "A2": "A2 - Elementary",
        "B1": "B1 - Intermediate",
        "B2": "B2 - Upper Intermediate",
        "C1": "C1 - Advanced",
        "C2": "C2 - Proficient",
    }
    return difficulty_map.get(cefr_level, f"{cefr_level} - Unknown")


# ---------------------------------------------------------------------------
@api.route("/article_simplification_levels", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def article_simplification_levels():
    """
    Get all available difficulty levels for an article (original + simplified versions).

    Query Parameters:
        article_id: ID of any article (original or simplified)

    Returns:
        JSON array with all available levels for the article family, including:
        - id: Article ID
        - cefr_level: CEFR level code (A1, A2, etc.)
        - difficulty: Human-readable difficulty label
        - title: Article title
        - is_original: Whether this is the original article
    """

    article_id = request.args.get("article_id", type=int)

    if not article_id:
        flask.abort(400, "article_id parameter required")

    # Find the article
    article = Article.find_by_id(article_id)
    if not article:
        flask.abort(404, "Article not found")

    # Get the original article (parent if this is simplified, otherwise itself)
    if article.parent_article_id:
        original_article = Article.find_by_id(article.parent_article_id)
        if not original_article:
            flask.abort(404, "Parent article not found")
    else:
        original_article = article

    # Build the response with all available levels
    levels = []

    # Add the original article - use the same logic as article_info()
    from zeeguu.core.language.fk_to_cefr import fk_to_cefr

    if original_article.cefr_level:
        original_cefr_level = original_article.cefr_level
    else:
        # Fallback to calculating from FK difficulty
        original_cefr_level = fk_to_cefr(original_article.get_fk_difficulty())

    levels.append(
        {
            "id": original_article.id,
            "cefr_level": original_cefr_level,
            "difficulty": _get_difficulty_label(original_cefr_level),
            "title": f"{original_article.title} (Original)",
            "is_original": True,
        }
    )

    # Add all simplified versions
    for simplified in original_article.simplified_versions:
        levels.append(
            {
                "id": simplified.id,
                "cefr_level": simplified.cefr_level,
                "difficulty": _get_difficulty_label(simplified.cefr_level),
                "title": f"{simplified.title} (Simplified)",
                "is_original": False,
            }
        )

    # Sort by CEFR level difficulty (A1 first, then A2, B1, etc.)
    cefr_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
    levels.sort(
        key=lambda x: (
            cefr_order.index(x["cefr_level"]) if x["cefr_level"] in cefr_order else 999
        )
    )

    return json_result(levels)
