#!/usr/bin/env python
"""
Cleanup old tokenization cache entries.

Run daily via cron to keep cache size manageable.
Entries older than 7 days are deleted - they'll be re-created on demand if needed.

Usage:
    python -m tools.cleanup_tokenization_cache [--days N]
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache

app = create_app()
app.app_context().push()


def main():
    parser = argparse.ArgumentParser(description="Cleanup old tokenization cache entries")
    parser.add_argument("--days", type=int, default=7, help="Delete entries older than N days (default: 7)")
    args = parser.parse_args()

    print(f"Deleting tokenization cache entries older than {args.days} days...")
    deleted = ArticleTokenizationCache.delete_older_than(db.session, days=args.days)
    print(f"Done. Deleted {deleted} entries.")


if __name__ == "__main__":
    main()
