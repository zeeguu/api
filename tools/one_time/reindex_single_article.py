#!/usr/bin/env python
"""
Debug script to re-index a single article and see what happens.

Run: python tools/one_time/reindex_single_article.py 4050335
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import Article
from zeeguu.core.elastic.indexing import (
    get_article_hit_in_es,
    document_from_article,
)
from zeeguu.core.elastic.basic_ops import es_update, es_index

article_id = int(sys.argv[1]) if len(sys.argv) > 1 else 4050335

article = Article.find_by_id(article_id)
print(f"Article {article_id}:")
print(f"  DB title: {article.title[:100]}")
print()

# Check what's in ES
hit = get_article_hit_in_es(article_id)
if hit:
    print(f"Found in ES:")
    print(f"  ES doc id: {hit.meta.id}")
    print(f"  ES title: {hit.title[:100] if hasattr(hit, 'title') else 'N/A'}")
    print()

    # Build new doc
    doc = document_from_article(article, db.session, hit.to_dict())
    print(f"New doc title: {doc['title'][:100]}")
    print()

    # Try update
    print("Updating ES...")
    res = es_update(id=hit.meta.id, body={"doc": doc})
    print(f"Update result: {res}")
    print()

    # Verify
    hit2 = get_article_hit_in_es(article_id)
    print(f"After update - ES title: {hit2.title[:100] if hasattr(hit2, 'title') else 'N/A'}")
else:
    print("Not found in ES - would create new")
