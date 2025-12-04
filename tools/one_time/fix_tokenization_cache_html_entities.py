#!/usr/bin/env python
"""
Delete tokenization cache for articles that had HTML entities fixed.
Cache will be regenerated on next request with correct titles.

Run: python tools/one_time/fix_tokenization_cache_html_entities.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import Article
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
from sqlalchemy import or_

print("Finding articles with quotes (that were fixed from HTML entities)...")

# Find article IDs that have quotes (were fixed)
article_ids = (
    db.session.query(Article.id)
    .filter(
        or_(
            Article.title.like('%"%'),
            Article.summary.like('%"%')
        )
    )
    .all()
)
article_ids = [a[0] for a in article_ids]

print(f"Found {len(article_ids)} articles")
print("Deleting their tokenization cache entries...")

deleted = (
    ArticleTokenizationCache.query
    .filter(ArticleTokenizationCache.article_id.in_(article_ids))
    .delete(synchronize_session=False)
)

db.session.commit()
print(f"Deleted {deleted} cache entries. They'll regenerate on next request.")
