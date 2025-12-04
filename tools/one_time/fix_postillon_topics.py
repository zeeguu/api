#!/usr/bin/env python
"""
One-time script to re-index Der Postillon articles in Elasticsearch
after their topics were fixed to Satire in the database.

Run: python tools/one_time/fix_postillon_topics.py
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

POSTILLON_FEED_ID = 214

articles = Article.query.filter(Article.feed_id == POSTILLON_FEED_ID).all()
print(f"Re-indexing {len(articles)} Der Postillon articles in Elasticsearch...")

skipped = 0
for i, article in enumerate(articles, 1):
    # Skip broken/empty articles
    if article.broken or not article.content or article.word_count == 0:
        skipped += 1
        continue

    try:
        create_or_update_article(article, db.session)
    except Exception as e:
        print(f"  Error on article {article.id}: {e}")
        skipped += 1
        continue

    if i % 50 == 0:
        print(f"  {i}/{len(articles)} done...")

print(f"Done! Re-indexed {len(articles) - skipped} articles, skipped {skipped}.")
