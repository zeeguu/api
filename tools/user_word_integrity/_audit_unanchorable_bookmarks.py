#!/usr/bin/env python
"""
Audit (and optionally delete) bookmarks whose `from` cannot be located
contiguously in the bookmark's context.

These are the 703020-family: typically multi-word IDIOM phrases whose tokens
appear non-contiguously in the source sentence (e.g. Danish "se i øjnene"
appearing as "se virkeligheden i øjnene"). The single-span anchor model
`(sentence_i, token_i, total_tokens)` can't represent such cases, and the
serialization-time correction in Bookmark.as_dictionary has no contiguous
match to fall back to either.

Distinct from `_fix_multiword_bookmark_positions.py`, which targets bookmarks
where the phrase IS contiguous but the stored position is wrong — those are
auto-corrected at serialization time now and don't need DB writes.

Default mode is dry-run; pass --delete to actually remove rows.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.model import Bookmark
from zeeguu.core.tokenization.word_position_finder import find_word_positions_in_text


def find_unanchorable():
    # Restrict to multi-word bookmarks — single tokens are rarely discontiguous
    # by definition. total_tokens > 1 OR NULL (legacy rows where the count
    # was never populated).
    query = Bookmark.query.filter(
        (Bookmark.total_tokens > 1) | (Bookmark.total_tokens == None)
    )
    bookmarks = query.all()
    print(f"Scanning {len(bookmarks)} multi-word bookmarks for unanchorable phrases...\n")

    unanchorable = []
    skipped = 0

    for i, bookmark in enumerate(bookmarks, start=1):
        if i % 500 == 0:
            print(f"  progress: {i}/{len(bookmarks)} — found {len(unanchorable)} unanchorable so far")

        try:
            word = bookmark.user_word.meaning.origin.content
            context = bookmark.context.get_content()
            if not word or not context or " " not in word:
                skipped += 1
                continue
            language = bookmark.user_word.meaning.origin.language

            result = find_word_positions_in_text(
                word, context, language, strict_matching=False
            )
            if len(result["found_positions"]) == 0:
                unanchorable.append({
                    "bookmark_id": bookmark.id,
                    "user_word_id": bookmark.user_word_id,
                    "word": word,
                    "context": (context[:120] + "...") if len(context) > 120 else context,
                    "phrase_type": bookmark.user_word.meaning.phrase_type,
                    "user_id": bookmark.user_word.user_id,
                    "lang": language.code,
                })
        except Exception as e:
            print(f"  ERR bookmark {bookmark.id}: {e}")
            skipped += 1

    print(f"\nDone. {len(unanchorable)} unanchorable, {skipped} skipped (non-multi-word / errors).\n")
    return unanchorable


def report(items, limit=30):
    if not items:
        print("No unanchorable bookmarks found.")
        return
    print(f"{'='*100}")
    print(f"Unanchorable multi-word bookmarks: {len(items)}")
    print(f"{'='*100}\n")
    by_lang = {}
    by_type = {}
    for it in items:
        by_lang[it["lang"]] = by_lang.get(it["lang"], 0) + 1
        pt = it["phrase_type"] or "(none)"
        by_type[pt] = by_type.get(pt, 0) + 1

    print(f"By language: {by_lang}")
    print(f"By phrase_type: {by_type}\n")

    for it in items[:limit]:
        print(f"  bookmark {it['bookmark_id']:>8}  user_word {it['user_word_id']:>8}  "
              f"[{it['lang']}, {it['phrase_type']}]  '{it['word']}'")
        print(f"    ctx: {it['context']}")
    if len(items) > limit:
        print(f"\n  ... and {len(items) - limit} more (re-run with --verbose to see all)")


def delete(items):
    if not items:
        print("Nothing to delete.")
        return 0
    print(f"\nDeleting {len(items)} bookmarks...")
    deleted = 0
    for it in items:
        try:
            b = Bookmark.find(it["bookmark_id"])
            db.session.delete(b)
            deleted += 1
            if deleted % 100 == 0:
                print(f"  deleted {deleted}/{len(items)}")
        except Exception as e:
            print(f"  ERR deleting bookmark {it['bookmark_id']}: {e}")
    db.session.commit()
    print(f"\nDeleted {deleted} bookmarks.")
    return deleted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true",
                        help="Actually delete the rows (default: dry-run).")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show every offending bookmark in the report.")
    args = parser.parse_args()

    items = find_unanchorable()
    report(items, limit=len(items) if args.verbose else 30)

    if args.delete:
        if not items:
            return
        answer = input(f"\nDelete {len(items)} bookmark rows? [y/N]: ")
        if answer.lower() != "y":
            print("Aborted.")
            return
        delete(items)
    else:
        if items:
            print("\nDry-run only. Pass --delete to remove these rows.")


if __name__ == "__main__":
    main()
