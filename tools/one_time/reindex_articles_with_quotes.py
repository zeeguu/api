#!/usr/bin/env python
"""
Re-index articles that have quotes in title/summary (likely fixed from &quot;).
Processes newest to oldest.

Run: python tools/one_time/reindex_articles_with_quotes.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import Article
from zeeguu.core.elastic.indexing import create_or_update_article
from sqlalchemy import or_

print("Finding articles with quotes in title or summary...")

articles = (
    Article.query
    .filter(
        or_(
            Article.title.like('%"%'),
            Article.summary.like('%"%')
        )
    )
    .filter(Article.broken == 0)
    .order_by(Article.id.desc())  # newest first
    .all()
)

print(f"Found {len(articles)} articles to re-index")

fixed = 0
errors = 0

for i, article in enumerate(articles, 1):
    if not article.content:
        continue

    try:
        create_or_update_article(article, db.session)
        fixed += 1
    except Exception as e:
        print(f"  Error re-indexing {article.id}: {e}")
        errors += 1

    if i % 100 == 0:
        print(f"  {i}/{len(articles)} done...")

print(f"Done! Re-indexed {fixed} articles, {errors} errors.")
