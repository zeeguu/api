#!/usr/bin/env python
"""
Backfill: re-assess articles whose crawl-time assessment was damaged by the
Aug-2026 on-demand-simplification defects (commit 0d047e32):

  1. article_type enum write failure rolled back the WHOLE assessment, leaving
     articles with NO cefr_level (and no summary / level summaries).   [95d8cef3]
  2. a weak language directive made Haiku write ~half of summaries in English
     for non-English articles.                                          [7cd9d6ca]

Both are fixed in code now. This tool re-runs the SAME crawl-time assessment
(assess_summarize_and_classify) on the affected originals, which overwrites
cefr_level, article_type, summary, and every ArticleLevelSummary row (find_or_
create updates in place) — in the correct language, once 7cd9d6ca is DEPLOYED.

IMPORTANT: run this only AFTER the prompt fix (7cd9d6ca) is live on the server,
or it will just rewrite English summaries again. It imports the deployed prompt.

A candidate needs re-assessment if EITHER its cefr_level is missing (defect 1)
OR its stored summary is in the wrong language (defect 2 — judged by the shared
zeeguu.core.language.language_check, so this works for any language). Already-
correct articles are skipped so we don't burn LLM calls (and cap budget) on them.

--include-missing-summaries adds a third case: articles with no summary at all.
Off by default because that describes everything crawled before summaries
existed; turn it on right after audit_stored_article_languages.py --fix, which
empties the wrong-language ones.

Usage (inside the api container), DRY-RUN first:
    python tools/backfill_reassess_summaries.py --language da --since 2026-08-13
    python tools/backfill_reassess_summaries.py --language da --since 2026-08-13 --apply
    python tools/backfill_reassess_summaries.py --language da --since 2026-08-13 --apply --limit 20
"""
import argparse

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.language.language_check import language_mismatch
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.llm_services.simplification_and_classification import (
    assess_summarize_and_classify,
)

session = db.session


def wrong_language(text, language_code):
    """
    True only when the summary is confidently in another language.

    Was a hand-rolled Danish-vs-English stopword count; now the same check the
    generation path uses, so this works for every language and agrees with what
    tools/audit_stored_article_languages.py reports.
    """
    return language_mismatch(text, language_code) is not None


def main():
    p = argparse.ArgumentParser(description="Re-assess damaged article summaries")
    p.add_argument(
        "--language",
        help="language code. Default: every language — audit_stored_article_languages.py "
        "--fix runs across all of them, and a single-language default silently "
        "backfilled a fraction of what it emptied.",
    )
    p.add_argument("--since", default="2026-08-01", help="published_time >= this date")
    p.add_argument("--apply", action="store_true", help="actually re-assess (else dry-run)")
    p.add_argument(
        "--include-missing-summaries",
        action="store_true",
        help="also re-assess articles that have no summary at all. Off by default: "
        "a missing summary is normal for anything crawled before summaries existed, "
        "so this widens the run far beyond the damaged set. Turn it on right after "
        "audit_stored_article_languages.py --fix, which is what empties them.",
    )
    p.add_argument(
        "--only",
        choices=["no_cefr", "wrong_language", "no_summary"],
        help="re-assess only articles needing it for THIS reason. Reasons are not "
        "equally sized: no_cefr covers every article demand-aware assessment has "
        "never looked at — 11840 of 22582 on 18 Aug 2026 — while the set emptied by "
        "audit_stored_article_languages.py --fix was 51. Without this, repairing "
        "those 51 costs 233x what it should, and --limit cannot substitute because "
        "it slices an id-ordered list that no_cefr dominates.",
    )
    p.add_argument("--limit", type=int, default=0, help="cap number processed (0 = no cap)")
    p.add_argument("--provider", default="anthropic")
    args = p.parse_args()

    lang = None
    if args.language:
        lang = Language.query.filter_by(code=args.language).first()
        if not lang:
            print(f"Unknown language code: {args.language}")
            return

    candidates = Article.query
    if lang:
        candidates = candidates.filter(Article.language_id == lang.id)
    candidates = (
        candidates.filter(Article.parent_article_id.is_(None))
        .filter(Article.simplification_ai_generator_id.is_(None))
        .filter(Article.published_time >= args.since)
        .filter((Article.broken.is_(None)) | (Article.broken == 0))
        .filter((Article.deleted.is_(None)) | (Article.deleted == 0))
        .order_by(Article.id.desc())
        .all()
    )

    need = []
    n_no_cefr = n_wrong_language = n_no_summary = 0
    for a in candidates:
        if a.get_word_count() < 100:
            continue
        reason = None
        if not a.cefr_level:
            reason = "no_cefr"
            n_no_cefr += 1
        elif a.language and wrong_language(a.summary or "", a.language.code):
            reason = "wrong_language"
            n_wrong_language += 1
        elif args.include_missing_summaries and not a.summary:
            # The ones audit_stored_article_languages.py --fix emptied. Opt-in:
            # without the flag this would also sweep in every article crawled
            # before summaries existed, which is a lot of LLM calls for nothing.
            reason = "no_summary"
            n_no_summary += 1
        if reason and (args.only is None or reason == args.only):
            need.append((a, reason))

    scope = lang.name if lang else "all languages"
    print(f"\n=== Backfill re-assess: {scope} since {args.since} ===")
    print(f"candidates scanned: {len(candidates)}")
    print(
        f"need re-assessment: {len(need)}  (no_cefr={n_no_cefr}, "
        f"wrong_language={n_wrong_language}, no_summary={n_no_summary}"
        + (f"; --only {args.only}" if args.only else "") + ")"
    )
    if args.limit:
        need = need[: args.limit]
        print(f"limited to: {len(need)}")

    if not args.apply:
        print("\n[dry-run] no changes made. Sample of what would be re-assessed:")
        for a, reason in need[:15]:
            print(f"  [{a.id}] {reason:>16}  {(a.title or '')[:70]}")
        print("\nRe-run with --apply to perform the re-assessment.")
        return

    print(f"\nApplying to {len(need)} articles via {args.provider} ...\n")
    ok = skipped = failed = 0
    for i, (a, reason) in enumerate(need, 1):
        try:
            assess_summarize_and_classify(session, a, simplification_provider=args.provider)
            ok += 1
            tag = "OK"
        except Exception as e:
            msg = str(e)
            if msg.startswith("PAYWALL") or msg.startswith("ADVERTORIAL"):
                skipped += 1
                tag = f"SKIP ({msg.split(':')[0]})"
            else:
                failed += 1
                tag = f"FAIL: {msg[:80]}"
            session.rollback()
        print(f"  [{i}/{len(need)}] article {a.id} ({reason}) -> {tag}")

    print(f"\n=== DONE: {ok} re-assessed, {skipped} skipped (paywall/advertorial), {failed} failed ===")


if __name__ == "__main__":
    main()
