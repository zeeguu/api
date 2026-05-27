#!/usr/bin/env python
"""
Remove Elasticsearch article docs whose article no longer exists in MySQL.

The article pruner (tools/prune_old_articles.py) and anonymize_users.py delete
articles in SQL only, so pruned articles linger in the ES "zeeguu" index and can
surface in search as results that 404 when opened. This sweep reconciles the
index against MySQL:

  - load every live article id (SELECT id FROM article),
  - scan the index for docs that have an `article_id` field (i.e. article docs;
    video/other docs have no article_id and are left untouched),
  - delete (by ES _id) every article doc whose article_id is not a live id.

Idempotent. Dry-run by default.

Usage:
  python tools/reconcile_es_articles.py            # report how many would go
  python tools/reconcile_es_articles.py --execute  # actually delete them
"""
import os
os.environ["PRELOAD_STANZA"] = "false"

import sys

import zeeguu.core
from sqlalchemy import text
from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan, bulk
from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX

execute = "--execute" in sys.argv

app = create_app_for_scripts()
app.app_context().push()
db_session = zeeguu.core.model.db.session

print(f"=== reconcile_es_articles ({'EXECUTE' if execute else 'DRY-RUN'}) — index '{ES_ZINDEX}' ===")

print("Loading live article ids from MySQL...")
live = set(r[0] for r in db_session.execute(text("SELECT id FROM article")))
print(f"  live articles in MySQL: {len(live):,}")

es = Elasticsearch(ES_CONN_STRING)
print(f"  total docs in ES index: {es.count(index=ES_ZINDEX)['count']:,}")

stats = {"article_docs": 0, "orphaned": 0}


def orphan_delete_actions():
    """Yield a bulk delete action for each article doc whose article is gone."""
    for hit in scan(
        es,
        index=ES_ZINDEX,
        query={"query": {"exists": {"field": "article_id"}}, "_source": ["article_id"]},
    ):
        stats["article_docs"] += 1
        aid = hit["_source"].get("article_id")
        if aid is None or aid in live:
            continue
        stats["orphaned"] += 1
        yield {"_op_type": "delete", "_index": ES_ZINDEX, "_id": hit["_id"]}


if execute:
    ok, errors = bulk(es, orphan_delete_actions(), raise_on_error=False, stats_only=False)
    print(f"  scanned {stats['article_docs']:,} article docs")
    print(f"  deleted {stats['orphaned']:,} orphaned ES docs ({ok} bulk-ok)")
    if errors:
        print(f"  {len(errors)} delete errors; first: {errors[0]}")
else:
    for _ in orphan_delete_actions():
        pass  # just exhaust the generator to count
    print(f"  scanned {stats['article_docs']:,} article docs")
    print(f"  {stats['orphaned']:,} are orphaned (article gone) — would delete.")
    print("  Re-run with --execute to delete them.")
