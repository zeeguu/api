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

for i, article in enumerate(articles, 1):
    create_or_update_article(article, db.session)
    if i % 50 == 0:
        print(f"  {i}/{len(articles)} done...")

print(f"Done! Re-indexed {len(articles)} articles.")
