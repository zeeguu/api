#!/usr/bin/env python
"""
Write article_type into the Elasticsearch documents of recent `general`
articles, so the News feed leaves them out.

The News query excludes documents whose article_type is 'general'. New
articles get the field when they are indexed (the crawler labels them first),
but documents indexed before the field existed have none, and so stay on News
until they age out. Only the 'general' ones need it: a document without the
field is treated as news anyway.

A partial update of one field: no re-embedding, no other field touched.

Usage:
  python tools/backfill_es_article_type.py                 # dry run, 14 days
  python tools/backfill_es_article_type.py --days 30 --execute
"""

import argparse
from datetime import datetime, timedelta

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import Article
from zeeguu.core.model.db import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.elastic.basic_ops import es_get_es_id_from_article_id, es_update

# The News feed decays recency on a 1-day scale, so two weeks covers what a
# learner can still scroll to.
DEFAULT_DAYS = 14


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--execute", action="store_true", help="write to ES (default: dry run)")
    args = parser.parse_args()

    since = datetime.now() - timedelta(days=args.days)
    ids = [
        row[0]
        for row in db.session.query(Article.id)
        .filter(Article.article_type == "general")
        .filter(Article.parent_article_id.is_(None))
        .filter(Article.published_time >= since)
        .order_by(Article.id)
        .all()
    ]
    print(f"{len(ids)} general articles published since {since:%Y-%m-%d}")

    updated = not_indexed = 0
    for i, article_id in enumerate(ids, 1):
        es_id = es_get_es_id_from_article_id(article_id)
        if not es_id:
            not_indexed += 1
            continue
        if args.execute:
            es_update(id=es_id, body={"doc": {"article_type": "general"}})
        updated += 1
        if i % 500 == 0:
            print(f"  {i}/{len(ids)}")

    verb = "updated" if args.execute else "would update"
    print(f"{verb} {updated}; not in the index: {not_indexed}")
    if not args.execute:
        print("Dry run. Re-run with --execute to write.")


if __name__ == "__main__":
    main()
