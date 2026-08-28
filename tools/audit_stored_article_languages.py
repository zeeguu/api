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
    LevelAdaptedArticleText.summary     the per-level feed-card blurbs; these only
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

--fix drops what is wrong rather than rewriting it:

  - article.summary is nulled, along with the cached tokenized copy of it (that
    cache is only ever written when empty, so a stale one would outlive the
    regeneration and keep rendering);
  - bad LevelAdaptedArticleText rows are deleted, with the bookmark anchors that
    reference them (a real FK, no cascade) removed first;
  - child articles are marked broken (LLM_WRONG_LANGUAGE), which takes a
    simplified one out of available_simplified_versions and a translated one out of
    the #translated-from URL cache, so the next reader at that language+level
    gets a fresh one.

Regenerating the summaries themselves is the job of
tools/backfill_reassess_summaries.py — run it after this, on the same
--language/--since window, with --include-missing-summaries so it picks up the
ones emptied here. The exact command is printed at the end of a --fix run.
"""

import argparse
from collections import Counter
from datetime import date, timedelta

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.language.language_check import language_mismatch, describe_mismatches
from zeeguu.core.model.article import Article
from zeeguu.core.model.article_broken_code_map import LowQualityTypes
from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText
from zeeguu.core.model.level_adapted_article_summary_context import LevelAdaptedArticleSummaryContext
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
from zeeguu.core.model.language import Language

session = db.session


def describe(mismatch):
    return describe_mismatches([mismatch])


_lines = []


def out(text=""):
    _lines.append(text)


def flush():
    for line in _lines:
        print(line)
    _lines.clear()


def report(header, rows):
    out("=" * 78)
    out(f"{header}: {len(rows)} in the wrong language")
    out("=" * 78)
    for label, mismatch in rows[:40]:
        out(f"  {label}")
        out(f"      {describe(mismatch)}")
    if len(rows) > 40:
        out(f"  ... and {len(rows) - 40} more")
    out()


def report_by_crawl_day(originals, flagged_articles):
    """
    Summariser failures vs articles audited, per day the article was crawled.

    Counts only articles whose BODY is in the right language — an English article
    in a Dutch feed is not the summariser getting it wrong, and leaving those in
    smeared a constant background rate across every day of the chart, which is
    what made the real 14-15 Aug spike hard to see.

    A flat total cannot tell a fixed backlog from a leak that is still running,
    and that difference decides whether --fix is safe: nulling a summary whose
    generator is still broken just regenerates it wrong. The English-summary bug
    was fixed in 7cd9d6ca on 15 Aug 2026 — if the rate falls to zero after that
    day, what is left is history to be backfilled.
    """
    flagged_ids = {article.id for article in flagged_articles}
    audited, flagged = Counter(), Counter()
    for article in originals:
        when = article.crawled_at or article.published_time
        day = when.date().isoformat() if when else "unknown"
        audited[day] += 1
        if article.id in flagged_ids:
            flagged[day] += 1

    out("=" * 78)
    out("wrong-language summaries by crawl day")
    out("=" * 78)
    for day in sorted(audited):
        n, total = flagged[day], audited[day]
        out(f"  {day}   {n:4} / {total:4}  {100 * n / total:5.1f}%  {'#' * min(40, n)}")
    out()


def audit_original_summaries(articles):
    """article.summary vs the article's own language. Rows keyed by article id, so
    the body-check split below can filter them by identity."""
    wrong, wrong_articles = {}, []
    for article in articles:
        mismatch = language_mismatch(article.summary, article.language.code, "summary")
        if mismatch:
            wrong[article.id] = (
                f"[{article.id}] {(article.title or '')[:60]}",
                mismatch,
            )
            wrong_articles.append(article)
    return wrong, wrong_articles


def split_off_wrong_language_articles(flagged):
    """
    Of the articles whose summary flagged, which have a wrong-language BODY too?

    The two populations need opposite treatment and the summary check alone cannot
    tell them apart. A Dutch feed carrying an English Economist piece flags exactly
    like a Dutch article that was given an English summary — but nulling the
    first one's summary only regenerates a Dutch summary of English text, which is
    worse than what it replaced. Only the second is the summariser's bug; the first
    is feed contamination and wants LANGUAGE_DOES_NOT_MATCH_FEED instead.

    Bodies are checked only for what already flagged — a few dozen articles rather
    than every one scanned — because reading full text is the expensive part.
    """
    summary_only, whole_article, rows = [], [], []
    for article in flagged:
        mismatch = language_mismatch(
            article.get_content() or "", article.language.code, "article body"
        )
        if mismatch:
            whole_article.append(article)
            rows.append((f"[{article.id}] {(article.title or '')[:60]}", mismatch))
        else:
            summary_only.append(article)
    return summary_only, whole_article, rows


def rows_for(articles, rows_by_article):
    return [rows_by_article[article.id] for article in articles]


def audit_level_summaries(articles):
    """LevelAdaptedArticleText rows — the tappable per-level feed-card blurbs."""
    by_id = {article.id: article for article in articles}
    if not by_id:
        return [], []
    rows = LevelAdaptedArticleText.query.filter(
        LevelAdaptedArticleText.article_id.in_(list(by_id))
    ).all()

    wrong, wrong_rows = [], []
    for row in rows:
        article = by_id[row.article_id]
        mismatch = language_mismatch(row.summary, article.language.code, "level summary")
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
        mismatch = language_mismatch(text, article.language.code, "simplified article")
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
    p.add_argument(
        "--days",
        type=int,
        help="rolling window: published_time >= N days ago. Overrides --since. Use "
        "this from cron — a fixed --since date makes a nightly job re-scan an "
        "ever-growing set and it gets slower every day it runs.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="print nothing when there is nothing wrong, so cron mail means a real "
        "finding. Same convention as audit_audio_lesson_script_languages.py.",
    )
    p.add_argument(
        "--include-broken",
        action="store_true",
        help="also scan articles marked broken. Off by default: a broken article "
        "is already excluded from every feed, so reporting it is noise. Useful for "
        "auditing what the crawl-time filter caught, which is its own question.",
    )
    p.add_argument(
        "--until",
        help="published_time < this date. With --since, scopes --fix to one window "
        "— the 14-15 Aug summariser bug is worth fixing separately from the "
        "long-running background rate that predates it.",
    )
    p.add_argument("--limit", type=int, default=0, help="cap articles scanned (0 = no cap)")
    p.add_argument(
        "--fix",
        action="store_true",
        help="drop what is wrong (null summaries, delete level summaries, mark "
        "simplified articles broken). Reports only without it.",
    )
    args = p.parse_args()
    if args.days:
        args.since = (date.today() - timedelta(days=args.days)).isoformat()

    query = Article.query.filter(Article.published_time >= args.since).filter(
        (Article.deleted.is_(None)) | (Article.deleted == 0)
    )
    # broken == 0 is what the endpoints use for "a user can see this", so it is
    # what this tool scans. Without it the audit re-reports articles the crawl-time
    # filter already caught — every one of the 31 wrong-language articles found on
    # 18 Aug 2026 was already broken=100, so all of them were noise dressed up as a
    # finding. Anything that DOES surface here is an escape from that filter, which
    # is the signal worth having.
    if not args.include_broken:
        query = query.filter(Article.broken == 0)
    if args.until:
        query = query.filter(Article.published_time < args.until)
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

    # Article.language_id is nullable, and a language-less row would take the
    # whole scan down on article.language.code. There is nothing to check them
    # against anyway.
    without_language = [a for a in articles if a.language is None]
    if without_language:
        out(f"Skipping {len(without_language)} article(s) with no language set")
        articles = [a for a in articles if a.language is not None]

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

    out(f"\nMode: {'FIX' if args.fix else 'REPORT ONLY'}")
    out(
        f"Scanning {len(originals)} originals, {len(simplified)} simplified and "
        f"{len(translated)} translated children "
        f"({args.language or 'all languages'}, since {args.since})\n"
    )

    originals_by_id = {article.id: article for article in originals}

    wrong_summaries, summary_articles = audit_original_summaries(originals)
    summary_articles, wrong_language_articles, wrong_language_rows = (
        split_off_wrong_language_articles(summary_articles)
    )
    report("article.summary (the summariser wrote the wrong language)",
           rows_for(summary_articles, wrong_summaries))
    report("the ARTICLE itself is in the wrong language — do NOT regenerate, "
           "these want marking broken", wrong_language_rows)

    wrong_level_summaries, level_summary_rows = audit_level_summaries(originals)
    report("LevelAdaptedArticleText.summary", wrong_level_summaries)

    wrong_simplified, simplified_articles = audit_child_articles(simplified)
    report("simplified children (same language as parent)", wrong_simplified)

    wrong_translated, translated_articles = audit_child_articles(translated)
    report("translated children (judged against their own language)", wrong_translated)

    level_summary_articles = [
        originals_by_id[row.article_id]
        for row in level_summary_rows
        if row.article_id in originals_by_id
    ]
    report_by_crawl_day(originals, summary_articles + level_summary_articles)

    bad_children = simplified_articles + translated_articles
    total = (
        len(summary_articles)
        + len(wrong_level_summaries)
        + len(wrong_simplified)
        + len(wrong_translated)
    )
    if wrong_language_articles:
        out(
            f"Leaving {len(wrong_language_articles)} article(s) alone: their body is "
            f"in the wrong language too, so regenerating the summary would only "
            f"produce a summary of foreign text. Mark them "
            f"{LowQualityTypes.LANGUAGE_DOES_NOT_MATCH_FEED} instead.\n"
        )

    found_something = bool(total or wrong_language_articles)
    if args.quiet and not found_something:
        return

    if not total:
        out("Nothing stored in the wrong language" +
            (" that regenerating would fix." if wrong_language_articles else "."))
        out("(Remember: titles and short summaries can't be judged at all.)")
        flush()
        return

    if not args.fix:
        out(f"{total} wrong-language items. Re-run with --fix to drop them.")
        flush()
        return

    # Everything below destroys data, so say what was found BEFORE doing it: if a
    # fix run dies halfway, the report of what it was working from is already out.
    flush()

    # Null the wrong summaries; the article keeps its assessment.
    #
    # The tokenized copy has to go with it. ArticleTokenizationCache only ever
    # writes tokenized_summary when it is empty (`if article.summary and not
    # cache.tokenized_summary`) and nothing else invalidates it — so leaving it
    # in place would survive the regeneration below and keep rendering the old
    # wrong-language tokens as the card's interactive summary.
    for article in summary_articles:
        article.summary = None
        session.add(article)
        cache = ArticleTokenizationCache.get_for_article(session, article.id)
        if cache and cache.tokenized_summary:
            cache.tokenized_summary = None
            session.add(cache)

    # Bookmarks anchor to a SPECIFIC level summary (LevelAdaptedArticleSummaryContext
    # holds a real FK with no cascade), so the anchors have to go first or the
    # delete fails on the constraint and takes the whole batch down with it.
    # They anchor into text we are throwing away, so there is nothing to keep.
    if level_summary_rows:
        summary_ids = [row.id for row in level_summary_rows]
        anchors = LevelAdaptedArticleSummaryContext.query.filter(
            LevelAdaptedArticleSummaryContext.level_adapted_article_text_id.in_(summary_ids)
        ).all()
        for anchor in anchors:
            session.delete(anchor)
        session.flush()
        for row in level_summary_rows:
            session.delete(row)

    session.commit()

    # Marked broken (not deleted): a reader who already has this article open
    # keeps it, while available_simplified_versions (same-language children) and the
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
        f" --since {args.since} --include-missing-summaries --apply"
    )


if __name__ == "__main__":
    main()
