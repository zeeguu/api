#!/usr/bin/env python
"""
Migration script to backfill available_cefr_levels field for existing articles in Elasticsearch.

This script:
1. Iterates through all original articles (parent_article_id IS NULL)
2. Computes available_cefr_levels from the article's cefr_level + all simplified versions
3. Updates the ES document with the new field

Usage:
    source ~/.venvs/z_env/bin/activate && python -m tools.update_es_available_cefr_levels
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from tqdm import tqdm

from zeeguu.core.model import Article
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.elastic.indexing import get_article_hit_in_es

# Configuration
BATCH_SIZE = 100
DRY_RUN = False  # Set to True to preview without updating


def compute_available_cefr_levels(article):
    """Compute available CEFR levels for an article (original + simplified versions)."""
    levels = []

    if article.cefr_level:
        levels.append(article.cefr_level)

    for simplified in article.simplified_versions:
        if simplified.cefr_level:
            levels.append(simplified.cefr_level)

    return levels


def generate_update_actions(articles, es):
    """Generate bulk update actions for ES."""
    for article in articles:
        try:
            # Get the ES document ID
            hit = get_article_hit_in_es(article.id)
            if not hit:
                print(f"  [SKIP] Article {article.id} not found in ES")
                continue

            es_id = hit.meta.id
            available_levels = compute_available_cefr_levels(article)

            yield {
                "_op_type": "update",
                "_index": ES_ZINDEX,
                "_id": es_id,
                "doc": {
                    "available_cefr_levels": available_levels
                }
            }
        except Exception as e:
            print(f"  [ERROR] Article {article.id}: {e}")


def main():
    print("=" * 60)
    print("Backfilling available_cefr_levels in Elasticsearch")
    print("=" * 60)

    if DRY_RUN:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    es = Elasticsearch(ES_CONN_STRING)
    print(f"Connected to ES: {ES_CONN_STRING}")

    # Get all original articles (not simplified versions)
    print("\nQuerying original articles from database...")
    original_articles = (
        Article.query
        .filter(Article.parent_article_id == None)
        .filter(Article.broken != 1)
        .all()
    )

    total_count = len(original_articles)
    print(f"Found {total_count} original articles to update")

    # Count articles with/without CEFR levels
    with_levels = sum(1 for a in original_articles if a.cefr_level or any(s.cefr_level for s in a.simplified_versions))
    without_levels = total_count - with_levels
    print(f"  - With CEFR levels: {with_levels}")
    print(f"  - Without CEFR levels: {without_levels}")

    if DRY_RUN:
        print("\n[DRY RUN] Would update these articles:")
        for article in original_articles[:10]:
            levels = compute_available_cefr_levels(article)
            print(f"  Article {article.id}: {levels}")
        if total_count > 10:
            print(f"  ... and {total_count - 10} more")
        return

    # Process in batches
    print(f"\nUpdating ES documents in batches of {BATCH_SIZE}...")
    success_count = 0
    error_count = 0

    for i in tqdm(range(0, total_count, BATCH_SIZE)):
        batch = original_articles[i:i + BATCH_SIZE]
        actions = list(generate_update_actions(batch, es))

        if actions:
            try:
                success, errors = bulk(es, actions, raise_on_error=False)
                success_count += success
                if errors:
                    error_count += len(errors)
                    for error in errors[:3]:  # Show first 3 errors
                        print(f"  [ERROR] {error}")
            except Exception as e:
                print(f"  [BATCH ERROR] {e}")
                error_count += len(actions)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total articles processed: {total_count}")
    print(f"Successfully updated: {success_count}")
    print(f"Errors: {error_count}")

    if without_levels > 0:
        print(f"\nWARNING: {without_levels} articles have no CEFR levels assigned.")
        print("These articles will have empty available_cefr_levels and won't appear in filtered results.")


if __name__ == "__main__":
    main()
