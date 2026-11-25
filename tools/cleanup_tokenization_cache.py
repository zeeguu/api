#!/usr/bin/env python
"""
Cleanup tokenization cache entries.

Two modes:

  --days N        Age sweep. Run daily via cron to keep cache size manageable.
                  Entries older than 7 days are deleted (default).

  --language CODE Re-tokenize everything cached in one language, regardless
                  of age. Use after a change to tokenization itself -- an MWE
                  rule, a lexicon entry, a parser upgrade. Covers all four
                  token caches; see zeeguu/core/tokenization/retokenize.py.

The age sweep only touches articles; the first reader of each one pays the
usual tokenization cost.

Usage:
    python -m tools.cleanup_tokenization_cache [--days N]
    python -m tools.cleanup_tokenization_cache --language da [--dry-run]

On the server, run --language in the run_task container, which talks to
stanza_crawl instead of the Stanza service live readers use (tens of
thousands of calls for Danish):
    docker compose run --rm run_task python -m tools.cleanup_tokenization_cache --language da
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


def retokenize_language(code, dry_run):
    from zeeguu.core.model.language import Language
    from zeeguu.core.tokenization import retokenize

    language = Language.find(code)
    for what, n in retokenize.count_cached(db.session, language).items():
        print(f"{'Would re-tokenize' if dry_run else 'Re-tokenizing'} {n} '{code}' {what}")
    if dry_run:
        return

    retokenize.clear_rebuildable(db.session, language)
    print("Articles and pasted texts cleared; they re-tokenize on next read.")
    for what, run in (
        ("Bookmark contexts", retokenize.retokenize_bookmark_contexts),
        ("Level-adapted texts", retokenize.retokenize_level_adapted),
    ):
        done, kept = run(db.session, language)
        print(f"{what} re-tokenized: {done}, kept old tokens: {kept}.")


def main():
    parser = argparse.ArgumentParser(description="Cleanup tokenization cache entries")
    parser.add_argument("--days", type=int, default=7, help="Delete entries older than N days (default: 7)")
    parser.add_argument("--language", help="Delete all entries for this language code (e.g. da)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be deleted, change nothing")
    args = parser.parse_args()

    if args.language:
        retokenize_language(args.language, args.dry_run)
        return

    if args.dry_run:
        print("--dry-run is only implemented for --language.")
        return

    print(f"Deleting tokenization cache entries older than {args.days} days...")
    deleted = ArticleTokenizationCache.delete_older_than(db.session, days=args.days)
    print(f"Done. Deleted {deleted} entries.")


if __name__ == "__main__":
    main()
