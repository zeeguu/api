#!/usr/bin/env python
"""
Cleanup tokenization cache entries.

Two modes:

  --days N        Age sweep. Run daily via cron to keep cache size manageable.
                  Entries older than 7 days are deleted (default).

  --language CODE Drop every entry for one language, regardless of age. Use
                  after a change to tokenization itself -- a new MWE lexicon
                  entry, a parser upgrade -- since nothing else invalidates
                  these rows and an article tokenized before the change keeps
                  its old grouping until the age sweep reaches it.

Either way the entries are re-created on demand on the next read, at the usual
tokenization cost for the first reader of each article.

Usage:
    python -m tools.cleanup_tokenization_cache [--days N]
    python -m tools.cleanup_tokenization_cache --language da [--dry-run]
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache

app = create_app_for_scripts()
app.app_context().push()


def main():
    parser = argparse.ArgumentParser(description="Cleanup tokenization cache entries")
    parser.add_argument("--days", type=int, default=7, help="Delete entries older than N days (default: 7)")
    parser.add_argument("--language", help="Delete all entries for this language code (e.g. da)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be deleted, change nothing")
    args = parser.parse_args()

    if args.language:
        count = ArticleTokenizationCache.count_for_language(db.session, args.language)
        if args.dry_run:
            print(f"Would delete {count} '{args.language}' tokenization cache entries.")
            return
        print(f"Deleting {count} '{args.language}' tokenization cache entries...")
        deleted = ArticleTokenizationCache.delete_for_language(db.session, args.language)
        print(f"Done. Deleted {deleted} entries. They re-tokenize on next read.")
        return

    if args.dry_run:
        print("--dry-run is only implemented for --language.")
        return

    print(f"Deleting tokenization cache entries older than {args.days} days...")
    deleted = ArticleTokenizationCache.delete_older_than(db.session, days=args.days)
    print(f"Done. Deleted {deleted} entries.")


if __name__ == "__main__":
    main()
