#!/usr/bin/env python
"""
Assign story ids to recently published articles, so the feed collapses stories
that were crawled before story clustering went live. New articles get theirs at
indexing time (zeeguu.core.story_clustering.assign_story).

Goes through the articles in publication order, so each joins the story of an
earlier one, as during crawling. Reads the vectors from ES; no embedding calls.

Requires the 26-10-14--add_article_story_id migration.

Usage:
    python -m tools.backfill_story_ids --language fr            # dry run: print the stories
    python -m tools.backfill_story_ids --language fr --apply
    python -m tools.backfill_story_ids --hours 72 --apply       # all languages
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta

from elasticsearch import Elasticsearch

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.model import Article, Language
from zeeguu.core.story_clustering import (
    STORY_SIMILARITY_THRESHOLD,
    _nearest_recent_article,
    assign_story,
)


def sem_vecs(article_ids):
    es = Elasticsearch(ES_CONN_STRING)
    vectors = {}
    for i in range(0, len(article_ids), 500):
        chunk = article_ids[i : i + 500]
        res = es.search(
            index=ES_ZINDEX,
            body={
                "query": {"terms": {"article_id": chunk}},
                "_source": ["article_id", "sem_vec"],
                "size": len(chunk) * 2,
            },
        )
        for hit in res["hits"]["hits"]:
            if hit["_source"].get("sem_vec"):
                vectors[hit["_source"]["article_id"]] = hit["_source"]["sem_vec"]
    return vectors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", help="language code; all languages if omitted")
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    query = Article.query.filter(
        Article.published_time >= datetime.now() - timedelta(hours=args.hours),
        Article.parent_article_id.is_(None),
        Article.story_id.is_(None),
        (Article.broken == 0) | Article.broken.is_(None),
    )
    if args.language:
        query = query.filter(Article.language_id == Language.find(args.language).id)
    articles = query.order_by(Article.published_time).all()
    vectors = sem_vecs([a.id for a in articles])
    print(f"{len(articles)} articles, {len(vectors)} with a sem_vec in ES")

    stories = defaultdict(list)
    for a in articles:
        vec = vectors.get(a.id)
        if not vec:
            continue
        if args.apply:
            assign_story(a, vec, db.session)
            if a.story_id:
                stories[a.story_id].append((a, None))
            continue
        nearest = _nearest_recent_article(a, vec)
        if nearest and nearest[1] >= STORY_SIMILARITY_THRESHOLD:
            stories[nearest[0]].append((a, nearest[1]))

    for root_id, members in stories.items():
        root = Article.find_by_id(root_id)
        print(f"\n[{root_id}] {root.feed.title if root and root.feed else '?'}: "
              f"{root.title if root else '(gone)'}")
        for a, similarity in members:
            score = f"{similarity:.3f}" if similarity else ""
            print(f"  {score:>5} [{a.id}] {a.feed.title if a.feed else '?'}: {a.title}")

    joined = sum(len(m) for m in stories.values())
    verb = "joined" if args.apply else "would join"
    print(f"\n{joined} articles {verb} {len(stories)} earlier stories")
    if not args.apply:
        print("(dry run; members are matched to their nearest earlier article, "
              "which --apply then maps to that article's story)")


if __name__ == "__main__":
    main()
