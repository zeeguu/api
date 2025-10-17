#!/usr/bin/env python
"""
Backfill script to migrate existing CEFR assessments from article table to article_cefr_assessment table.

Migrates data from:
- article.cefr_level
- article.cefr_source
- article.cefr_assessed_by_user_id

To:
- article_cefr_assessment table (1:1 relationship with article)

Run this after applying the database migration for article_cefr_assessment table.

Usage:
    source ~/.venvs/z_env/bin/activate && python -m tools.backfill_cefr_assessments [--dry-run] [--limit N]
"""

import argparse
from datetime import datetime

from zeeguu.api.app import create_app
from zeeguu.core.model import db, Article, ArticleCefrAssessment
from zeeguu.logging import log

# Create Flask app and push context
app = create_app()
app.app_context().push()

db_session = db.session


def backfill_assessments(dry_run=False, limit=None):
    """
    Migrate existing CEFR assessments from article table to article_cefr_assessment table.

    Args:
        dry_run: If True, don't commit changes - just report what would be done
        limit: Maximum number of articles to process (for testing)

    Returns:
        Dict with statistics
    """
    log("=" * 80)
    log("CEFR Assessment Backfill Script (1:1 Architecture)")
    log("=" * 80)
    log(
        f"Mode: {'DRY RUN (no changes will be saved)' if dry_run else 'LIVE (changes will be saved)'}"
    )
    log("")

    # Query all articles with CEFR levels
    query = db_session.query(Article).filter(Article.cefr_level.isnot(None))

    if limit:
        query = query.limit(limit)
        log(f"Limiting to {limit} articles for testing")
        log("")

    articles = query.all()
    log(f"Found {len(articles)} articles with CEFR levels to migrate")
    log("")

    stats = {
        "total_articles": len(articles),
        "assessments_created": 0,
        "articles_with_source": 0,
        "llm_assessments": 0,
        "teacher_assessments": 0,
        "unknown_assessments": 0,
        "errors": 0,
    }

    for idx, article in enumerate(articles):
        if idx % 100 == 0 and idx > 0:
            log(f"  Processed {idx}/{len(articles)} articles...")

        try:
            # Check if assessment already exists (in case script is run multiple times)
            existing_assessment = (
                db_session.query(ArticleCefrAssessment)
                .filter_by(article_id=article.id)
                .first()
            )
            if existing_assessment:
                # Already migrated, skip
                continue

            # Determine assessment method from article data
            # We're only processing articles with cefr_level.isnot(None), so all have been assessed

            if article.parent_article_id:
                # Simplified article - level is the TARGET level (what we asked LLM to simplify TO)
                # Store in simplification_target_level, NOT llm_cefr_level
                assessment_method = "simplification_target"
                stats["articles_with_source"] += 1
            else:
                # Original article with CEFR level - was assessed by LLM during crawling
                # Try to determine which LLM was used
                if article.simplification_ai_generator_id:
                    # Query AIGenerator table to check model name
                    from zeeguu.core.model.ai_generator import AIGenerator

                    ai_gen = (
                        db_session.query(AIGenerator)
                        .filter_by(id=article.simplification_ai_generator_id)
                        .first()
                    )

                    if ai_gen and "anthropic" in ai_gen.model_name.lower():
                        assessment_method = "llm_assessed_anthropic"
                    else:
                        assessment_method = "llm_assessed_deepseek"
                else:
                    # No AI generator info - default to deepseek (most common)
                    assessment_method = "llm_assessed_deepseek"

                stats["articles_with_source"] += 1

            assessed_by_user_id = (
                article.cefr_assessed_by_user_id
                if hasattr(article, "cefr_assessed_by_user_id")
                else None
            )

            # Categorize assessments
            is_llm = assessment_method in [
                "llm_assessed_deepseek",
                "llm_assessed_anthropic",
            ]
            is_teacher = assessment_method in ["teacher_resolution", "teacher_manual"]
            is_simplification_target = assessment_method == "simplification_target"

            if is_llm:
                stats["llm_assessments"] += 1
            elif is_teacher:
                stats["teacher_assessments"] += 1
            elif is_simplification_target:
                stats["llm_assessments"] += 1  # Count as processed
            else:
                # Should not happen since we only query articles with cefr_level
                stats["unknown_assessments"] += 1

            if not dry_run:
                # Create assessment record
                assessment = ArticleCefrAssessment(article_id=article.id)

                # Store in appropriate column based on method
                if is_llm:
                    assessment.set_llm_assessment(article.cefr_level, assessment_method)
                elif is_teacher:
                    assessment.set_teacher_assessment(
                        article.cefr_level, assessment_method, assessed_by_user_id
                    )
                elif is_simplification_target:
                    # For simplified articles, store ONLY the target level
                    # (not as an LLM assessment - that would be conflating target with measurement)
                    assessment.simplification_target_level = article.cefr_level
                    # Don't set llm_cefr_level or ml_cefr_level here
                    # Those should be measured assessments, not targets

                    # Compute effective_cefr_level (will be just simplification_target_level since no ML yet)
                    assessment.update_effective_cefr_level()

                db_session.add(assessment)

            stats["assessments_created"] += 1

        except Exception as e:
            log(f"  ERROR processing article {article.id}: {str(e)}")
            stats["errors"] += 1
            continue

    # Commit all changes at once (if not dry run)
    if not dry_run and stats["assessments_created"] > 0:
        log("")
        log(f"Committing {stats['assessments_created']} new assessments to database...")
        db_session.commit()
        log("✓ Committed successfully")
    elif dry_run:
        log("")
        log("DRY RUN - Rolling back (no changes saved)")
        db_session.rollback()

    # Print statistics
    log("")
    log("=" * 80)
    log("MIGRATION STATISTICS")
    log("=" * 80)
    log(f"Total articles with CEFR levels: {stats['total_articles']}")
    log(f"  - With AI generator tracking: {stats['articles_with_source']}")
    log("")
    log(f"Assessments created: {stats['assessments_created']}")
    log(f"  - LLM assessments: {stats['llm_assessments']}")
    log(f"  - Teacher assessments: {stats['teacher_assessments']}")
    log(f"  - Unknown source: {stats['unknown_assessments']}")
    log("")
    log(f"Errors: {stats['errors']}")
    log("")

    if dry_run:
        log("✓ DRY RUN COMPLETE - No changes were saved")
        log("  Run without --dry-run to apply changes")
    else:
        log("✓ MIGRATION COMPLETE")

    log("=" * 80)

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backfill CEFR assessments from article table to article_cefr_assessment table"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (don't save changes, just report what would be done)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of articles to process (for testing)",
    )

    args = parser.parse_args()

    backfill_assessments(dry_run=args.dry_run, limit=args.limit)
