#!/usr/bin/env python
"""
Find summaries and simplified articles that were stored in the wrong language.

Between the on-demand-simplification rollout and 7cd9d6ca (Aug 15 2026) the
assess/summarize prompt conveyed the output language through a weak indirection,
and Haiku honoured it only about half the time for non-English articles. Nothing
errored — the assessment succeeded and an English summary was written onto a
Danish article — so the only way to find the residue is to look at what is
stored. New output is checked at generation time by
zeeguu.core.language.language_check; this tool covers the rows already in the DB.

Everything is checked against the language of the row it belongs to, never the
parent's — which is what makes this safe for cross-language shares:

    article.summary                 on originals
    ArticleLevelSummary.summary     the per-level feed-card blurbs; these only
                                    ever exist on originals (the assess step
                                    skips children), so they are always in the
                                    original's language
    child Article rows              title + summary + content

A child of an original is one of two things, and they are reported separately:

  - a **simplified** version — same language as the parent, a level adaptation.
  - a **translated** copy — a different language, created when an article is
    shared with a friend who is learning another language. It hangs off the same
    parent so the reader's "Original:" link works and so it coalesces per
    (original, language, level), but it is a legitimately German article under a
    Danish parent. It is judged against its OWN language: German here is right,
    not a defect. Scanning --language da therefore does not even see it; it
    shows up under --language de.

Titles are not checked on their own: under ~60 characters langdetect can't say
anything, so nearly all of them come back "can't judge" — which is NOT the same
as clean. Expect this tool to under-report.

Usage:
    python -m tools.audit_stored_article_languages --language da            # report only
    python -m tools.audit_stored_article_languages --language da --since 2026-07-01
    python -m tools.audit_stored_article_languages --language da --fix

--fix drops what is wrong rather than rewriting it: summaries are nulled and bad
level-summary rows deleted, so they regenerate; child articles are marked broken
(LLM_WRONG_LANGUAGE), which takes a simplified one out of
usable_simplified_versions and a translated one out of the #translated-from URL
cache, so the next reader at that language+level gets a fresh one. Regenerating
the summaries themselves is the job of tools/backfill_reassess_summaries.py —
run it after this, on the same --language/--since window.
"""

import argparse

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.language.language_check import check_language, describe_mismatches
from zeeguu.core.model.article import Article
from zeeguu.core.model.article_broken_code_map import LowQualityTypes
from zeeguu.core.model.article_level_summary import ArticleLevelSummary
from zeeguu.core.model.language import Language

session = db.session


def describe(mismatch):
    return describe_mismatches([mismatch])


def report(header, rows):
    print("=" * 78)
    print(f"{header}: {len(rows)} in the wrong language")
    print("=" * 78)
    for label, mismatch in rows[:40]:
        print(f"  {label}")
        print(f"      {describe(mismatch)}")
    if len(rows) > 40:
        print(f"  ... and {len(rows) - 40} more")
    print()


def audit_original_summaries(articles):
    """article.summary vs the article's own language."""
    wrong, wrong_articles = [], []
    for article in articles:
        mismatch = check_language(article.summary, article.language.code, "summary")
        if mismatch:
            wrong.append((f"[{article.id}] {(article.title or '')[:60]}", mismatch))
            wrong_articles.append(article)
    return wrong, wrong_articles


def audit_level_summaries(articles):
    """ArticleLevelSummary rows — the tappable per-level feed-card blurbs."""
    by_id = {article.id: article for article in articles}
    if not by_id:
        return [], []
    rows = ArticleLevelSummary.query.filter(
        ArticleLevelSummary.article_id.in_(list(by_id))
    ).all()

    wrong, wrong_rows = [], []
    for row in rows:
        article = by_id[row.article_id]
        mismatch = check_language(row.summary, article.language.code, "level summary")
        if mismatch:
            wrong.append((f"[article {row.article_id}] {row.cefr_level} summary", mismatch))
            wrong_rows.append(row)
    return wrong, wrong_rows


def audit_child_articles(children):
    """A child article, judged on its whole body — not just its summary."""
    wrong, wrong_articles = [], []
    for article in children:
        text = " ".join(
            filter(None, [article.title, article.summary, article.get_content()])
        )
        mismatch = check_language(text, article.language.code, "simplified article")
        if mismatch:
            wrong.append(
                (
                    f"[{article.id}] {article.cefr_level} {article.language.code} of "
                    f"{article.parent_article_id} — {(article.title or '')[:50]}",
                    mismatch,
                )
            )
            wrong_articles.append(article)
    return wrong, wrong_articles


def main():
    p = argparse.ArgumentParser(description="Find wrong-language stored article text")
    p.add_argument("--language", help="language code, e.g. da (default: all)")
    p.add_argument(
        "--since",
        default="2026-08-01",
        help="published_time >= this date (default 2026-08-01, the bug window)",
    )
    p.add_argument("--limit", type=int, default=0, help="cap articles scanned (0 = no cap)")
    p.add_argument(
        "--fix",
        action="store_true",
        help="drop what is wrong (null summaries, delete level summaries, mark "
        "simplified articles broken). Reports only without it.",
    )
    args = p.parse_args()

    query = Article.query.filter(Article.published_time >= args.since).filter(
        (Article.deleted.is_(None)) | (Article.deleted == 0)
    )
    if args.language:
        language = Language.find(args.language)
        if not language:
            print(f"Unknown language code: {args.language}")
            return
        query = query.filter(Article.language_id == language.id)
    query = query.order_by(Article.id.desc())
    if args.limit:
        query = query.limit(args.limit)
    articles = query.all()

    originals = [a for a in articles if a.parent_article_id is None]
    children = [a for a in articles if a.parent_article_id is not None]
    # Same language as the parent = a level adaptation. Different language = a
    # friend-share translation, which is *supposed* to be in another language and
    # is only wrong if it doesn't match its own.
    def is_level_adaptation(child):
        parent = child.parent_article
        return parent is not None and child.language_id == parent.language_id

    simplified = [a for a in children if is_level_adaptation(a)]
    translated = [a for a in children if not is_level_adaptation(a)]

    print(f"\nMode: {'FIX' if args.fix else 'REPORT ONLY'}")
    print(
        f"Scanning {len(originals)} originals, {len(simplified)} simplified and "
        f"{len(translated)} translated children "
        f"({args.language or 'all languages'}, since {args.since})\n"
    )

    wrong_summaries, summary_articles = audit_original_summaries(originals)
    report("article.summary", wrong_summaries)

    wrong_level_summaries, level_summary_rows = audit_level_summaries(originals)
    report("ArticleLevelSummary.summary", wrong_level_summaries)

    wrong_simplified, simplified_articles = audit_child_articles(simplified)
    report("simplified children (same language as parent)", wrong_simplified)

    wrong_translated, translated_articles = audit_child_articles(translated)
    report("translated children (judged against their own language)", wrong_translated)

    bad_children = simplified_articles + translated_articles
    total = (
        len(wrong_summaries)
        + len(wrong_level_summaries)
        + len(wrong_simplified)
        + len(wrong_translated)
    )
    if not total:
        print("Nothing stored in the wrong language.")
        print("(Remember: titles and short summaries can't be judged at all.)")
        return

    if not args.fix:
        print(f"{total} wrong-language items. Re-run with --fix to drop them.")
        return

    # Null the wrong summaries; the article keeps its assessment.
    for article in summary_articles:
        article.summary = None
        session.add(article)

    for row in level_summary_rows:
        session.delete(row)

    session.commit()

    # Marked broken (not deleted): a reader who already has this article open
    # keeps it, while usable_simplified_versions (same-language children) and the
    # #translated-from URL cache (cross-language ones) both stop handing it out,
    # so the next request at that language+level regenerates.
    for article in bad_children:
        article.set_as_broken(session, LowQualityTypes.LLM_WRONG_LANGUAGE)

    print(
        f"Fixed: nulled {len(summary_articles)} article summaries, deleted "
        f"{len(level_summary_rows)} level summaries, marked "
        f"{len(simplified_articles)} simplified and {len(translated_articles)} "
        f"translated children broken."
    )
    print(
        "\nNow regenerate the summaries:\n"
        f"    python tools/backfill_reassess_summaries.py --language {args.language or 'da'}"
        f" --since {args.since} --apply"
    )


if __name__ == "__main__":
    main()
