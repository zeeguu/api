#!/usr/bin/env python
"""
Calibrate "same story" detection across feeds before building it.

Le Figaro and HuffPost both ran "Francis Renaud en garde à vue" a few hours
apart and both landed in the same French feed. The crawler's simhash check
does not catch that: it only compares articles of the *same* feed, and
simhash only matches near-verbatim text. The planned fix is a story_id
assigned at indexing time by nearest-neighbour search on an embedding.

This tool answers, read-only, the two questions that decide the design:

  1. Which text to embed: the full article (the existing ES `sem_vec`) or
     title + LLM summary (short, outlet-neutral, names up front)?
  2. Where the threshold between "same story" and "same topic" lies, and
     whether a shared-proper-noun check is needed on top.

For every pair of originals in one language, from different feeds, published
within --window-hours of each other, it computes both cosines plus the proper
nouns the two title+summary texts share, and prints:

  - a histogram of pair counts per similarity bucket, for both embeddings;
  - random sample pairs per bucket (titles, feeds, both scores, shared names)
    to eyeball where the boundary is;
  - the pairs on which the two embeddings disagree most;
  - pairs whose titles contain --find (e.g. "Renaud"), to check a known case.

All pairs at or above --csv-floor on either score go to --csv for a closer look.

Summaries count as LLM-written when the article has a cefr_level (the assess
step sets both); otherwise they are the RSS blurb / content-prefix fallback,
and pairs involving one are marked with '*'.

Cost: one call to the embedding service per article (title + summary). The
full-article vectors are read from ES, not recomputed.

Usage (prod, without deploying the script):
    ssh zeeguu.org 'docker exec -i api-zapi-1 python - --language fr --days 3 --find Renaud' \\
        < tools/calibrate_story_clustering.py
"""

import argparse
import csv
import random
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import numpy as np
from elasticsearch import Elasticsearch

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.model import Article, Language
from zeeguu.core.semantic_vector_api import get_embedding_from_text

app = create_app_for_scripts()
app.app_context().push()

BUCKETS = [round(0.50 + 0.05 * i, 2) for i in range(10)]  # 0.50 .. 0.95

# Capitalised words that are not names: articles/determiners/prepositions that
# start a title or follow a quote mark. Only needs to be good enough to
# separate "both mention Francis Renaud" from "both mention Le".
NOT_NAMES = {
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "en", "au", "aux",
    "il", "elle", "ils", "elles", "on", "ce", "cette", "ces", "son", "sa", "ses",
    "pour", "par", "sur", "dans", "avec", "après", "avant", "selon", "mais",
    "the", "a", "an", "of", "in", "on", "and", "der", "die", "das", "ein", "eine",
    "den", "det", "en", "et", "og", "i", "el", "los", "las", "lo", "il", "lo",
}
# Elided prefixes: "L'acteur", "d'Orélien", "l’IA"
ELISION = re.compile(r"^[ldjnmstcq][’']", re.IGNORECASE)
WORD = re.compile(r"[\w’'-]+")


def proper_nouns(text):
    """Capitalised words that do not start a sentence, lowercased."""
    names = set()
    sentence_start = True
    for token in WORD.findall(text or ""):
        word = ELISION.sub("", token)
        if (
            word[:1].isupper()
            and not sentence_start
            and len(word) >= 3
            and word.lower() not in NOT_NAMES
        ):
            names.add(word.lower())
        sentence_start = False
    # A word right after a full stop is a sentence start, so also drop
    # anything that only ever appears there.
    for sentence in re.split(r"[.!?]\s+", text or ""):
        first = WORD.findall(sentence)[:1]
        if first:
            names.discard(ELISION.sub("", first[0]).lower())
    return names


def unit(v):
    if v is None:
        return None
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else None


def full_article_vectors(article_ids):
    """The `sem_vec` already stored in ES, by article id."""
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
            src = hit["_source"]
            if src.get("sem_vec"):
                vectors[src["article_id"]] = unit(src["sem_vec"])
    return vectors


def summary_text(article):
    return f"{article.title}\n{article.summary or ''}".strip()


def summary_vectors(articles, language_name, workers):
    def embed(article):
        return article.id, unit(get_embedding_from_text(summary_text(article), language_name))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(embed, articles))


def bucket_of(score):
    if score is None or score < BUCKETS[0]:
        return None
    return max(b for b in BUCKETS if score >= b)


def fmt(score):
    return "  -  " if score is None else f"{score:.3f}"


def print_pair(p):
    star = "*" if p["fallback"] else " "
    print(
        f"  {star}full {fmt(p['full'])}  summ {fmt(p['summ'])}  "
        f"names {len(p['shared'])} {sorted(p['shared'])[:6]}"
    )
    print(f"     [{p['a'].id}] {p['a'].feed.title}: {p['a'].title}")
    print(f"     [{p['b'].id}] {p['b'].feed.title}: {p['b'].title}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--language", default="fr")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--window-hours", type=int, default=48)
    parser.add_argument("--samples", type=int, default=4, help="pairs shown per bucket")
    parser.add_argument("--find", help="also print pairs whose titles both contain this")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--csv", default="/tmp/story_calibration.csv")
    parser.add_argument("--csv-floor", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    random.seed(args.seed)

    language = Language.find(args.language)
    since = datetime.now() - timedelta(days=args.days)
    articles = (
        Article.query.filter(
            Article.language_id == language.id,
            Article.published_time >= since,
            Article.parent_article_id.is_(None),
            Article.feed_id.isnot(None),
            (Article.broken == 0) | Article.broken.is_(None),
            (Article.deleted == 0) | Article.deleted.is_(None),
        )
        .order_by(Article.published_time)
        .all()
    )
    print(f"{len(articles)} {args.language} originals published since {since:%Y-%m-%d %H:%M}")
    if len(articles) < 2:
        return

    full = full_article_vectors([a.id for a in articles])
    print(f"  {len(full)} have a full-article sem_vec in ES")
    summ = summary_vectors(articles, language.name.lower(), args.workers)
    print(f"  {sum(v is not None for v in summ.values())} got a title+summary embedding")
    llm_summary = {a.id: a.cefr_level is not None for a in articles}
    print(f"  {sum(llm_summary.values())} have an LLM summary, the rest the fallback blurb")
    names = {a.id: proper_nouns(summary_text(a)) for a in articles}

    window = timedelta(hours=args.window_hours)
    pairs = []
    for i, a in enumerate(articles):
        for b in articles[i + 1 :]:
            if b.published_time - a.published_time > window:
                break  # sorted by time
            if a.feed_id == b.feed_id:
                continue
            fa, fb, sa, sb = full.get(a.id), full.get(b.id), summ.get(a.id), summ.get(b.id)
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "full": float(fa @ fb) if fa is not None and fb is not None else None,
                    "summ": float(sa @ sb) if sa is not None and sb is not None else None,
                    "shared": names[a.id] & names[b.id],
                    "fallback": not (llm_summary[a.id] and llm_summary[b.id]),
                }
            )
    print(f"{len(pairs)} cross-feed pairs within {args.window_hours}h\n")

    print("Pairs per bucket (score >= bucket)")
    print(f"  {'bucket':>6}  {'full':>7}  {'summary':>7}")
    for b in BUCKETS:
        n_full = sum(bucket_of(p["full"]) == b for p in pairs)
        n_summ = sum(bucket_of(p["summ"]) == b for p in pairs)
        print(f"  {b:>6.2f}  {n_full:>7}  {n_summ:>7}")

    for key, label in (("summ", "TITLE+SUMMARY"), ("full", "FULL ARTICLE")):
        print(f"\n=== Samples by {label} similarity ('*' = involves a fallback summary) ===")
        by_bucket = defaultdict(list)
        for p in pairs:
            by_bucket[bucket_of(p[key])].append(p)
        for b in reversed(BUCKETS):
            if not by_bucket[b]:
                continue
            shown = random.sample(by_bucket[b], min(args.samples, len(by_bucket[b])))
            print(f"\n-- {label} >= {b:.2f} ({len(by_bucket[b])} pairs)")
            for p in sorted(shown, key=lambda p: -p[key]):
                print_pair(p)

    both = [p for p in pairs if p["full"] is not None and p["summ"] is not None]
    print("\n=== Summary much higher than full article ===")
    for p in sorted(both, key=lambda p: p["full"] - p["summ"])[:8]:
        print_pair(p)
    print("\n=== Full article much higher than summary ===")
    for p in sorted(both, key=lambda p: p["summ"] - p["full"])[:8]:
        print_pair(p)

    if args.find:
        needle = args.find.lower()
        print(f"\n=== Pairs where both titles contain '{args.find}' ===")
        for p in pairs:
            if needle in p["a"].title.lower() and needle in p["b"].title.lower():
                print_pair(p)

    kept = [
        p for p in pairs
        if max(p["full"] or 0, p["summ"] or 0) >= args.csv_floor
    ]
    with open(args.csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["full", "summ", "shared_names", "fallback", "id_a", "feed_a",
                    "title_a", "id_b", "feed_b", "title_b", "hours_apart"])
        for p in sorted(kept, key=lambda p: -(p["summ"] or 0)):
            a, b = p["a"], p["b"]
            w.writerow([
                fmt(p["full"]).strip(), fmt(p["summ"]).strip(),
                " ".join(sorted(p["shared"])), int(p["fallback"]),
                a.id, a.feed.title, a.title, b.id, b.feed.title, b.title,
                round((b.published_time - a.published_time).total_seconds() / 3600, 1),
            ])
    print(f"\n{len(kept)} pairs >= {args.csv_floor} on either score written to {args.csv}")


if __name__ == "__main__":
    main()
