#!/usr/bin/env python
"""
THROWAWAY test harness (safe to delete) — compares the CURRENT summary rule
against a PROPOSED "must-add-facts-beyond-the-headline" rule, on real stored
Romanian articles, using the same Haiku client the ingestion pipeline uses.

It does NOT write anything. It only reads articles + calls Haiku and prints a
side-by-side so we can eyeball whether the new prompt turns "useless" summaries
(headline restated) into ones that actually add information.

Run in the env that has the DB + ANTHROPIC_TEXT_SIMPLIFICATION_KEY:

    python -m tools.test_summary_prompt --lang ro --count 6
    python -m tools.test_summary_prompt --lang ro --keywords Noname Mureșan --count 6
"""

import argparse

from sqlalchemy.orm import load_only

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.llm_services.haiku_client import haiku_completion

MAX_CONTENT_CHARS = 4000  # bound input like the "truncate long articles" idea

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


def old_prompt(title, content, lang_name):
    # Mirrors the current ORIGINAL_SUMMARY rule in
    # zeeguu/core/llm_services/prompts/article_simplification.py
    return f"""You are summarizing a news article for a language-learning reading app.

Title: {title}

Article:
{content}

Write a concise plain text summary (no markdown, no bold/italic) in {lang_name}, maximum 25 words. State the article's key facts/claims directly. DO NOT use meta-preambles like "The article tells about...", "This article is about...". Just state the content as if reporting it yourself.

Output only the summary text, nothing else."""


def new_prompt(title, content, lang_name):
    return f"""You are writing the feed summary for a news article in a language-learning reading app. The reader sees the TITLE plus this summary on a card and decides whether it's worth reading. In the kiosk reader the summary is ALL the reader gets — there is no full article — so it must stand on its own.

Title: {title}

Article:
{content}

Write the summary in {lang_name}, following these rules:
- ADD information the title does not already contain: the specific names, numbers, reasons, consequences, or context the headline gestures at but does not state. If the headline assumes knowledge (a referent, an event, an acronym, "a swap with X"), briefly supply what it is.
- NEVER restate or paraphrase the headline. If a reader could guess your summary from the title alone, it has failed — rewrite it.
- Lead with the concrete facts: who, what, how many, the outcome.
- 2 to 4 sentences, scaled to the article — short items stay ~1-2 sentences, longer or denser articles up to ~4 (hard cap ~70 words).
- Paraphrase in your own words. Do NOT copy sentences or distinctive phrases verbatim from the article, and do NOT include any direct quotes.
- Plain text only (no markdown). No preambles like "This article is about...".

Output only the summary text, nothing else."""


def pick_articles(lang, count, keywords):
    picked, seen = [], set()

    # Prefer the specific articles named on the command line (the two cards).
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

    # Fill up with the most recent Romanian articles that have a summary.
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
    ap.add_argument("--count", type=int, default=6)
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

            old = haiku_completion(old_prompt(a.title, content, lang_name), max_tokens=120, temperature=0.0)
            new = haiku_completion(new_prompt(a.title, content, lang_name), max_tokens=300, temperature=0.0)

            print("\n" + "=" * 90)
            print(f"[{i}] article_id={a.id}")
            print(f"TITLE   : {a.title}")
            print(f"STORED  : {a.summary}")
            print(f"OLD RULE: {old}")
            print(f"NEW RULE: {new}")

        print("\n" + "=" * 90)
        print("Done. (This tool wrote nothing to the DB.)")


if __name__ == "__main__":
    main()
