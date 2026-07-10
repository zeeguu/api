#!/usr/bin/env python

"""
One-off cleanup for web#1177: mark already-ingested non-article puzzle pages
(Guardian crosswords/sudoku/etc) as broken so they drop out of feeds.

Readability scrapes a crossword's clue list (~140-250 words), which clears the
90-word minimum, so these slipped past the length filter and into feeds. Going
forward they are blocked at ingestion by SOURCE_CONTENT_FILTERS; this tool
backfills the ones already in the DB.

It reuses the exact same predicate as the crawler
(`should_filter_by_source_keywords`), so the set cleaned here is identical to
the set the crawler now rejects — "Crossword editor's desk:" feature articles
do NOT match and are left untouched.

Usage:
    python -m tools.mark_non_article_puzzles_broken            # dry run (default)
    python -m tools.mark_non_article_puzzles_broken --commit   # actually mark broken
"""

import argparse

from sqlalchemy import or_

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import Article, db
from zeeguu.core.model.article_broken_code_map import LowQualityTypes
from zeeguu.core.content_retriever.article_downloader import (
    should_filter_by_source_keywords,
)
from zeeguu.core.elastic.indexing import remove_from_index


def run(commit=False):
    print("=" * 80)
    print("MARK NON-ARTICLE PUZZLES AS BROKEN (web#1177)")
    print(f"Mode: {'LIVE (will modify DB + ES)' if commit else 'DRY RUN'}")
    print("-" * 80)

    # Narrow to plausible candidates, then let the crawler predicate make the
    # exact decision (keeps this tool and the crawler in lockstep).
    candidates = (
        Article.query.filter((Article.broken == 0) | (Article.broken == None))
        .filter(Article.parent_article_id == None)  # not a simplified copy
        .filter(
            or_(
                Article.title.like("%crossword%"),
                Article.title.like("%Sudoku%"),
                Article.title.like("%wordsearch%"),
                Article.title.like("%Wordiply%"),
            )
        )
        .all()
    )

    marked = 0
    for article in candidates:
        url = article.url.as_string() if article.url else ""
        should_filter, reason = should_filter_by_source_keywords(url, article.title)
        if not should_filter:
            continue  # e.g. "Crossword editor's desk:" — a real article

        marked += 1
        prefix = "Would mark" if not commit else "Marking"
        print(f"{prefix} {article.id}: {article.title[:60]}  [{reason}]")

        if commit:
            article.set_as_broken(db.session, LowQualityTypes.NON_ARTICLE)
            remove_from_index(article)

    print("-" * 80)
    print(f"Candidates scanned: {len(candidates)}")
    print(f"{'Marked broken' if commit else 'Would mark broken'}: {marked}")
    if not commit:
        print("\nDRY RUN — no changes made. Re-run with --commit to apply.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually mark articles broken (default is a dry run)",
    )
    args = parser.parse_args()

    app = create_app_for_scripts()
    with app.app_context():
        run(commit=args.commit)


if __name__ == "__main__":
    main()
