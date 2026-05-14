#!/usr/bin/env python
"""
Extract candidate MWE phrases from a Universal Dependencies treebank
using the `fixed` dependency relation.

UD's `fixed` is exactly the relation that catches grammaticised
prepositional/adverbial idioms ("in spite of", "på trods af",
"im Hinblick auf") — i.e. the long tail Stanza-based detection
misses and our hand-curated lexicons under
`api/zeeguu/core/mwe/lexicons/` only sparsely cover.

USAGE
=====
1. Download a CoNLL-U treebank (e.g. UD_Danish-DDT):
       https://universaldependencies.org/#download
2. Run:
       python tools/extract_mwes_from_ud.py path/to/da_ddt-ud-train.conllu

It prints a deduplicated, frequency-sorted list of candidate phrases.
Pipe to `sort -u` and review by hand before adding to the lexicon —
this script extracts CANDIDATES, not finished lexicon entries.

This is a one-shot tool. It does not touch the DB and does not
require Flask app context.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path


def parse_conllu(path: Path):
    """Yield sentences as lists of token dicts."""
    sentence = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                if sentence:
                    yield sentence
                    sentence = []
                continue
            if line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 8:
                continue
            tok_id = cols[0]
            # Skip multiword token ranges and empty nodes
            if "-" in tok_id or "." in tok_id:
                continue
            try:
                head = int(cols[6])
            except ValueError:
                continue
            sentence.append({
                "id": int(tok_id),
                "form": cols[1],
                "lemma": cols[2],
                "upos": cols[3],
                "head": head,
                "dep": cols[7],
            })
        if sentence:
            yield sentence


def extract_fixed_phrases(sentence):
    """
    For every token with dep=fixed, walk up to the head, collect all
    tokens that also have dep=fixed pointing at the same head, sort
    by id, and emit the surface phrase.

    UD `fixed` annotates flat fixed-grammar idioms head-initially:
    the first word is the head, subsequent words attach with fixed.
    """
    by_id = {t["id"]: t for t in sentence}
    # Group fixed-dependents by their head id
    fixed_deps_by_head: dict[int, list[int]] = {}
    for t in sentence:
        if t["dep"] == "fixed":
            fixed_deps_by_head.setdefault(t["head"], []).append(t["id"])

    phrases = []
    for head_id, dep_ids in fixed_deps_by_head.items():
        if head_id not in by_id:
            continue
        ids = sorted([head_id, *dep_ids])
        words = [by_id[i]["form"].lower() for i in ids]
        # Skip phrases containing punctuation or digits
        if any(not w.replace("'", "").replace("-", "").isalpha() for w in words):
            continue
        phrases.append(" ".join(words))
    return phrases


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("conllu", type=Path, help="Path to a .conllu treebank file")
    ap.add_argument(
        "--min-count", type=int, default=2,
        help="Drop phrases seen fewer than N times (default: 2)",
    )
    args = ap.parse_args()

    if not args.conllu.exists():
        print(f"File not found: {args.conllu}", file=sys.stderr)
        sys.exit(1)

    counter: Counter[str] = Counter()
    for sent in parse_conllu(args.conllu):
        for phrase in extract_fixed_phrases(sent):
            counter[phrase] += 1

    for phrase, n in counter.most_common():
        if n < args.min_count:
            continue
        print(f"{n}\t{phrase}")


if __name__ == "__main__":
    main()
