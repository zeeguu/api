#!/usr/bin/env python
"""
Re-index articles that have HTML entities in ES.
Queries ES for &quot; etc and re-indexes from the (already fixed) DB.

Run: python tools/one_time/reindex_articles_with_html_entities.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.model import Article
from zeeguu.core.elastic.indexing import create_or_update_article

es = Elasticsearch(ES_CONN_STRING)

# Search for articles with HTML entities in title or summary
entities = ['&quot;', '&amp;', '&lt;', '&gt;', '&apos;']

article_ids = set()

for entity in entities:
    print(f"Searching for '{entity}' in ES...")

    # Search in title
    s = Search(using=es, index=ES_ZINDEX).query("match_phrase", title=entity)
    s = s.params(size=10000)
    response = s.execute()
    for hit in response:
        if hasattr(hit, 'article_id'):
            article_ids.add(hit.article_id)

    # Search in summary
    s = Search(using=es, index=ES_ZINDEX).query("match_phrase", summary=entity)
    s = s.params(size=10000)
    response = s.execute()
    for hit in response:
        if hasattr(hit, 'article_id'):
            article_ids.add(hit.article_id)

print(f"Found {len(article_ids)} articles with HTML entities in ES")

if not article_ids:
    print("Nothing to re-index!")
    sys.exit(0)

print("Re-indexing from DB...")
fixed = 0
errors = 0

for i, article_id in enumerate(article_ids, 1):
    article = Article.find_by_id(article_id)
    if not article:
        print(f"  Article {article_id} not found in DB")
        errors += 1
        continue

    if article.broken or not article.content:
        continue

    try:
        create_or_update_article(article, db.session)
        fixed += 1
    except Exception as e:
        print(f"  Error re-indexing {article_id}: {e}")
        errors += 1

    if i % 50 == 0:
        print(f"  {i}/{len(article_ids)} done...")

print(f"Done! Re-indexed {fixed} articles, {errors} errors.")
