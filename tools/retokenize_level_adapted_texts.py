#!/usr/bin/env python
"""
Re-tokenize the cached token streams on level-adapted article texts.

Why this exists separately from cleanup_tokenization_cache:

`ArticleTokenizationCache` is a cache in the ordinary sense -- delete a row and
the next read rebuilds it. `LevelAdaptedArticleText.tokenized_summary` and
`.tokenized_title` are not. They are written once, when the article is
simplified, and nothing regenerates them: both readers treat an empty column as
"this level has no tappable summary" and fall back to plain text
(`elastic_recommender._payload` is guarded by `if summary_tokens:`, and
`UserArticle` returns None). So clearing them would silently make previews
untappable, forever.

That means a change to tokenization or MWE detection has to *rewrite* these
rows, not invalidate them. Run this after cleanup_tokenization_cache, with the
same --language, or the article body picks up the change while the preview card
keeps showing the old grouping.

Usage:
    python -m tools.retokenize_level_adapted_texts --language da --dry-run
    python -m tools.retokenize_level_adapted_texts --language da
    python -m tools.retokenize_level_adapted_texts --article-id 4946174
"""
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText

app = create_app_for_scripts()
app.app_context().push()


def _groups(tokens):
    """The MWE groups in a token stream, as {group_id: "the words"}."""
    def walk(x):
        if isinstance(x, dict):
            yield x
        elif isinstance(x, list):
            for y in x:
                yield from walk(y)

    out = {}
    for t in walk(tokens or []):
        gid = t.get("mwe_group_id")
        if gid:
            out.setdefault(gid, []).append(t.get("text"))
    return {k: " ".join(v) for k, v in out.items()}


def main():
    parser = argparse.ArgumentParser(description="Re-tokenize level-adapted article texts")
    parser.add_argument("--language", help="Language code, e.g. da")
    parser.add_argument("--article-id", type=int, help="Only this article's levels")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change, write nothing")
    parser.add_argument("--limit", type=int, help="Stop after N rows (for a first look)")
    args = parser.parse_args()

    if not args.language and not args.article_id:
        parser.error("give --language or --article-id")

    q = LevelAdaptedArticleText.query
    if args.article_id:
        q = q.filter(LevelAdaptedArticleText.article_id == args.article_id)
    if args.language:
        language = Language.find(args.language)
        q = q.join(Article, Article.id == LevelAdaptedArticleText.article_id).filter(
            Article.language_id == language.id
        )
    q = q.order_by(LevelAdaptedArticleText.id)
    if args.limit:
        q = q.limit(args.limit)

    rows = q.all()
    print(f"{len(rows)} level-adapted rows to consider"
          f"{' (DRY RUN)' if args.dry_run else ''}")

    # The enricher logs a line per call at INFO. Over thousands of rows that
    # buries the diffs this tool exists to show, so quieten it unless the run
    # actually goes wrong.
    logging.getLogger("zeeguu.core.mwe.enricher").setLevel(logging.WARNING)

    from zeeguu.core.mwe import tokenize_for_reading

    changed = failed = 0
    for i, row in enumerate(rows, 1):
        article = Article.find_by_id(row.article_id)
        if not article:
            continue

        row_changed = False
        for field in ("summary", "title"):
            text = getattr(row, field)
            if not text or not text.strip():
                continue
            try:
                fresh = tokenize_for_reading(text, article.language, mode="stanza")
            except Exception as e:
                print(f"  row {row.id} {field}: tokenization failed: {e}")
                failed += 1
                continue

            before = _groups(getattr(row, f"get_tokenized_{field}")())
            after = _groups(fresh)
            if before == after:
                continue

            row_changed = True
            gone = {k: v for k, v in before.items() if v not in after.values()}
            new = {k: v for k, v in after.items() if v not in before.values()}
            print(f"  row {row.id} (article {row.article_id}, {row.cefr_level}) {field}:")
            if gone:
                print(f"      was: {sorted(gone.values())}")
            if new:
                print(f"      now: {sorted(new.values())}")

            if not args.dry_run:
                setattr(row, f"tokenized_{field}", fresh)
                db.session.add(row)

        if row_changed:
            changed += 1
        if not args.dry_run and i % 50 == 0:
            db.session.commit()
            print(f"  ... committed through row {i}/{len(rows)}")

    if not args.dry_run:
        db.session.commit()

    verb = "would change" if args.dry_run else "changed"
    print(f"Done. {changed} rows {verb}; {failed} tokenization failures.")


if __name__ == "__main__":
    main()
