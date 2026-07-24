#!/usr/bin/env python
"""
THROWAWAY test harness (safe to delete) — compares the CURRENT kiosk summary
against a PLAIN / elder-friendly summary rule, on real stored Romanian articles,
using the same Haiku client the ingestion pipeline uses.

Motivation: the current summary rule (see backfill_summaries.py / the
ORIGINAL_SUMMARY prompt) is tuned for language *learners* deciding whether to
click through — dense, novel-fact-first, up to ~70 words, "never restate the
title". For an elderly native reader where the summary IS the whole thing
(kiosk, no full article), that is hard to read. This harness lets us eyeball a
plainer rule: short sentences, one idea each, common words, rounded numbers,
calm framing — to test with a real reader (e.g. read it aloud, hand him the
tablet) whether the plain version lands better.

It does NOT write anything. It only reads articles + calls Haiku and prints a
side-by-side.

Run in the env that has the DB + ANTHROPIC_TEXT_SIMPLIFICATION_KEY:

    python -m tools.test_plain_summary_for_elderly --lang ro --count 8
    python -m tools.test_plain_summary_for_elderly --lang ro --keywords pensii spital --count 8
"""

import argparse

from sqlalchemy.orm import load_only

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db  # noqa: F401  (imported for app-context parity with sibling tools)
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.llm_services.haiku_client import haiku_completion

MAX_CONTENT_CHARS = 4000  # bound input like the sibling harnesses

# Load ONLY these columns. The code checkout may have columns (e.g. crawled_at)
# that this DB hasn't migrated yet; a default ORM load would SELECT them and
# blow up. These are the ones we actually need + source_id so get_content works.
_SAFE_COLS = (
    Article.id,
    Article.title,
    Article.summary,
    Article.content,
    Article.published_time,
    Article.language_id,
    Article.source_id,
)


def current_prompt(title, content, lang_name):
    # Mirrors the CURRENT kiosk rule in backfill_summaries.py / ORIGINAL_SUMMARY.
    return f"""You are writing the feed summary for a news article in a language-learning reading app. The reader sees the TITLE plus this summary on a card. In the kiosk reader the summary is ALL the reader gets — there is no full article — so it must stand on its own.

Title: {title}

Article:
{content}

Write the summary in {lang_name}, following these rules:
- ADD information the title does not already contain: the specific names, numbers, reasons, consequences, or context the title implies but does not state.
- NEVER restate or paraphrase the title.
- Use ONLY facts stated in the article above.
- Lead with the concrete facts: who, what, how many, the outcome.
- 2 to 4 sentences, scaled to the article (hard cap ~70 words).
- Plain text only (no markdown). No preambles like "This article is about...".

Output only the summary text, nothing else."""


def plain_prompt(title, content, lang_name):
    # Elder-friendly rule. The point is COMPREHENSION for an older native reader,
    # not novelty for a learner. Redundancy with the title is FINE here.
    return f"""You are writing a news summary in {lang_name} for an ELDERLY reader who may tire easily and find dense text hard to follow. This summary is all they read — there is no full article. The goal is that they understand it on the first read, without effort, and feel calm and informed.

Title: {title}

Article:
{content}

Write the summary in {lang_name}, following these rules:
- Use short, simple sentences. Aim for about 8 to 12 words per sentence. One idea per sentence.
- Use common, everyday words. Avoid jargon, abbreviations, acronyms, and foreign terms. If a term is unavoidable, say plainly what it means.
- Round numbers so they are easy to grasp ("almost 5 million" rather than "4,732,000"). Keep at most one or two numbers.
- State the main point first, plainly. It is fine to repeat words from the title — clarity matters more than novelty.
- Keep a calm, neutral tone. Do not use alarming or sensational wording.
- Use ONLY facts stated in the article above. Do not add anything from your own knowledge.
- 2 to 3 short sentences. Keep the whole thing under ~45 words.
- Plain text only (no markdown). No preambles like "This article is about...".

Output only the summary text, nothing else."""


def pick_articles(lang, count, keywords):
    picked, seen = [], set()

    for kw in keywords or []:
        q = (
            Article.query.options(load_only(*_SAFE_COLS))
            .filter(Article.language_id == lang.id)
            .filter(Article.title.ilike(f"%{kw}%"))
            .order_by(Article.published_time.desc())
            .limit(3)
        )
        for a in q:
            if a.id not in seen:
                picked.append(a)
                seen.add(a.id)

    recent = (
        Article.query.options(load_only(*_SAFE_COLS))
        .filter(Article.language_id == lang.id)
        .filter(Article.summary.isnot(None))
        .order_by(Article.published_time.desc())
        .limit(count * 4)
    )
    for a in recent:
        if len(picked) >= count:
            break
        if a.id not in seen:
            picked.append(a)
            seen.add(a.id)

    return picked[:count]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ro")
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--keywords", nargs="*", default=[])
    args = ap.parse_args()

    app = create_app_for_scripts()
    with app.app_context():
        lang = Language.find(args.lang)
        lang_name = lang.name
        articles = pick_articles(lang, args.count, args.keywords)

        if not articles:
            print(f"No {args.lang} articles found.")
            return

        for i, a in enumerate(articles, 1):
            try:
                content = a.get_content() or ""
            except Exception:
                content = a.content or ""  # fallback to the legacy content column
            content = content[:MAX_CONTENT_CHARS]
            if len(content) < 200:
                continue

            current = haiku_completion(
                current_prompt(a.title, content, lang_name), max_tokens=300, temperature=0.0
            )
            plain = haiku_completion(
                plain_prompt(a.title, content, lang_name), max_tokens=200, temperature=0.0
            )

            print("\n" + "=" * 90)
            print(f"[{i}] article_id={a.id}")
            print(f"TITLE  : {a.title}")
            print(f"CURRENT: {current}")
            print(f"PLAIN  : {plain}")

        print("\n" + "=" * 90)
        print("Done. (This tool wrote nothing to the DB.)")


if __name__ == "__main__":
    main()
