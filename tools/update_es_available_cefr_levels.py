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
DB_BATCH_SIZE = 10000  # How many articles to fetch from DB at once
ES_BATCH_SIZE = 100    # How many ES updates to batch together
DRY_RUN = False        # Set to True to preview without updating


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


def get_base_query():
    """Base query for original articles, ordered by most recent first."""
    return (
        Article.query
        .filter(Article.parent_article_id == None)
        .filter(Article.broken != 1)
        .order_by(Article.published_time.desc())
    )


def main():
    print("=" * 60)
    print("Backfilling available_cefr_levels in Elasticsearch")
    print("=" * 60)

    if DRY_RUN:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    es = Elasticsearch(ES_CONN_STRING)
    print(f"Connected to ES: {ES_CONN_STRING}")

    # Get total count first (fast query)
    print("\nCounting articles...")
    total_count = get_base_query().count()
    print(f"Found {total_count} original articles to update")

    if DRY_RUN:
        print("\n[DRY RUN] Would update first 10 articles:")
        for article in get_base_query().limit(10).all():
            levels = compute_available_cefr_levels(article)
            print(f"  Article {article.id}: {levels}")
        if total_count > 10:
            print(f"  ... and {total_count - 10} more")
        return

    # Process in batches - fetch from DB in chunks
    print(f"\nProcessing in batches of {DB_BATCH_SIZE} from DB, {ES_BATCH_SIZE} to ES...")
    success_count = 0
    error_count = 0
    offset = 0

    with tqdm(total=total_count) as pbar:
        while offset < total_count:
            # Fetch batch from database
            db_batch = get_base_query().offset(offset).limit(DB_BATCH_SIZE).all()

            if not db_batch:
                break

            # Process this DB batch in smaller ES batches
            for i in range(0, len(db_batch), ES_BATCH_SIZE):
                es_batch = db_batch[i:i + ES_BATCH_SIZE]
                actions = list(generate_update_actions(es_batch, es))

                if actions:
                    try:
                        success, errors = bulk(es, actions, raise_on_error=False)
                        success_count += success
                        if errors:
                            error_count += len(errors)
                    except Exception as e:
                        print(f"  [BATCH ERROR] {e}")
                        error_count += len(actions)

                pbar.update(len(es_batch))

            # Clear session to free memory
            db.session.expire_all()
            offset += DB_BATCH_SIZE

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total articles processed: {total_count}")
    print(f"Successfully updated: {success_count}")
    print(f"Errors: {error_count}")


if __name__ == "__main__":
    main()
