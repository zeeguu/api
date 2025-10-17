#!/usr/bin/env python
"""
Add ML CEFR assessments to recent articles that have no CEFR level.

This script finds articles from the last N days that:
- Have no cefr_level set in the article table
- Have no ArticleCefrAssessment record (or have one with no ML assessment)

For these articles, it runs the ML CEFR classifier and stores the result.

Usage:
    source ~/.venvs/z_env/bin/activate && python -m tools.add_ml_assessment_to_recent_articles [--days N] [--dry-run] [--limit N]

Examples:
    # Dry run - see what would be done for articles from last 30 days
    python -m tools.add_ml_assessment_to_recent_articles --days 30 --dry-run

    # Actually process articles from last 30 days
    python -m tools.add_ml_assessment_to_recent_articles --days 30

    # Process only 10 articles for testing
    python -m tools.add_ml_assessment_to_recent_articles --days 30 --limit 10
"""

import argparse
from datetime import datetime, timedelta

from zeeguu.api.app import create_app
from zeeguu.core.model import db, Article, ArticleCefrAssessment
from zeeguu.core.language.ml_cefr_classifier import predict_cefr_level
from zeeguu.logging import log

# Create Flask app and push context
app = create_app()
app.app_context().push()

db_session = db.session


def add_ml_assessments(days=30, dry_run=False, limit=None):
    """
    Add ML CEFR assessments to recent articles without CEFR levels.

    Args:
        days: Look at articles from the last N days (default: 30)
        dry_run: If True, don't commit changes - just report what would be done
        limit: Maximum number of articles to process (for testing)

    Returns:
        Dict with statistics
    """
    log("=" * 80)
    log("ML CEFR Assessment Backfill Script")
    log("=" * 80)
    log(
        f"Mode: {'DRY RUN (no changes will be saved)' if dry_run else 'LIVE (changes will be saved)'}"
    )
    log(f"Processing articles from the last {days} days")
    log("")

    # Calculate date threshold
    date_threshold = datetime.now() - timedelta(days=days)

    # Query articles without CEFR level from the last N days
    query = (
        db_session.query(Article)
        .filter(Article.cefr_level.is_(None))
        .filter(Article.published_time >= date_threshold)
        .filter(Article.broken == 0)  # Skip broken articles
        .filter(Article.deleted == 0)  # Skip deleted articles
        .filter(Article.parent_article_id.is_(None))  # Skip simplified versions
        .order_by(Article.published_time.desc())
    )

    if limit:
        query = query.limit(limit)
        log(f"Limiting to {limit} articles for testing")
        log("")

    articles = query.all()
    log(f"Found {len(articles)} articles without CEFR levels from the last {days} days")
    log("")

    stats = {
        "total_articles": len(articles),
        "ml_assessments_added": 0,
        "ml_assessments_failed": 0,
        "skipped_no_content": 0,
        "skipped_too_short": 0,
        "errors": 0,
    }

    for idx, article in enumerate(articles):
        if idx % 10 == 0 and idx > 0:
            log(f"  Processed {idx}/{len(articles)} articles...")

        try:
            # Skip articles without content
            if not article.get_content():
                stats["skipped_no_content"] += 1
                continue

            # Skip very short articles (likely broken)
            if article.get_word_count() < 50:
                stats["skipped_too_short"] += 1
                continue

            # Check if assessment already exists
            assessment = (
                db_session.query(ArticleCefrAssessment)
                .filter_by(article_id=article.id)
                .first()
            )

            # Skip if ML assessment already exists
            if assessment and assessment.ml_cefr_level:
                continue

            # Run ML CEFR prediction
            try:
                ml_level = predict_cefr_level(
                    article.get_content(),
                    article.language.code,
                    article.get_fk_difficulty(),
                    article.get_word_count(),
                )

                if ml_level:
                    if not dry_run:
                        # Create or update assessment record
                        if not assessment:
                            assessment = ArticleCefrAssessment(article_id=article.id)
                            db_session.add(assessment)

                        # Set ML assessment
                        assessment.set_ml_assessment(ml_level, "ml")

                        # Also update legacy article.cefr_level if not set
                        if not article.cefr_level:
                            article.cefr_level = ml_level
                            db_session.add(article)

                    stats["ml_assessments_added"] += 1

                    if idx < 5 or (idx % 50 == 0):  # Log details for first few and every 50th
                        log(
                            f"  Article {article.id}: '{article.title[:50]}...' -> {ml_level}"
                        )
                else:
                    stats["ml_assessments_failed"] += 1

            except Exception as e:
                log(f"  ERROR predicting CEFR for article {article.id}: {str(e)}")
                stats["ml_assessments_failed"] += 1
                continue

            # Commit every 50 articles to avoid huge transactions
            if not dry_run and idx > 0 and idx % 50 == 0:
                db_session.commit()

        except Exception as e:
            log(f"  ERROR processing article {article.id}: {str(e)}")
            stats["errors"] += 1
            continue

    # Final commit (if not dry run)
    if not dry_run and stats["ml_assessments_added"] > 0:
        log("")
        log(f"Committing {stats['ml_assessments_added']} new ML assessments to database...")
        db_session.commit()
        log("✓ Committed successfully")
    elif dry_run:
        log("")
        log("DRY RUN - Rolling back (no changes saved)")
        db_session.rollback()

    # Print statistics
    log("")
    log("=" * 80)
    log("STATISTICS")
    log("=" * 80)
    log(f"Total articles found: {stats['total_articles']}")
    log(f"  - Skipped (no content): {stats['skipped_no_content']}")
    log(f"  - Skipped (too short): {stats['skipped_too_short']}")
    log("")
    log(f"ML assessments added: {stats['ml_assessments_added']}")
    log(f"ML assessments failed: {stats['ml_assessments_failed']}")
    log(f"Other errors: {stats['errors']}")
    log("")

    if dry_run:
        log("✓ DRY RUN COMPLETE - No changes were saved")
        log("  Run without --dry-run to apply changes")
    else:
        log("✓ PROCESSING COMPLETE")

    log("=" * 80)

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add ML CEFR assessments to recent articles without CEFR levels"
    )

    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Process articles from the last N days (default: 30)",
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

    add_ml_assessments(days=args.days, dry_run=args.dry_run, limit=args.limit)
