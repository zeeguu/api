#!/usr/bin/env python
"""
Backfill article.summary with the new additive/grounded LLM summary for one
language, so the feed (especially the Romanian kiosk) shows the improved
summaries immediately instead of waiting for articles to be re-crawled.

The summary rule here MIRRORS ORIGINAL_SUMMARY in
zeeguu/core/llm_services/prompts/article_simplification.py — keep them in sync.
Only article.summary is touched (plus its now-stale tokenization cache row);
no simplified children are created, so this is cheap and side-effect-light.

DRY-RUN by default — prints OLD -> NEW and writes nothing. Pass --commit to apply.

    python -m tools.backfill_summaries --lang ro --count 200            # preview
    python -m tools.backfill_summaries --lang ro --count 200 --commit   # write
"""

import argparse

from sqlalchemy.orm import load_only

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
from zeeguu.core.llm_services.haiku_client import haiku_completion

MAX_CONTENT_CHARS = 4000  # bound input; news front-loads the facts

# Load ONLY these columns — the code checkout may have columns this DB hasn't
# migrated yet (e.g. crawled_at); a default ORM load would SELECT them and fail.
_SAFE_COLS = (
    Article.id,
    Article.title,
    Article.summary,
    Article.content,
    Article.published_time,
    Article.language_id,
    Article.source_id,
)


def summary_prompt(title, content, lang_name):
    return f"""You are writing the feed summary for a news article in a language-learning reading app. The reader sees the TITLE plus this summary on a card. In the kiosk reader the summary is ALL the reader gets — there is no full article — so it must stand on its own.

Title: {title}

Article:
{content}

Write the summary in {lang_name}, following these rules:
- ADD information the title does not already contain: the specific names, numbers, reasons, consequences, or context the headline implies but does not state. If the title assumes a referent (a person, event, acronym, "a swap with X"), briefly say what it is ONLY IF the article explains it.
- NEVER restate or paraphrase the title. If a reader could guess your summary from the title alone, rewrite it.
- Use ONLY facts stated in the article above. Do NOT add details from your own knowledge (dates, ages, place names, discographies) even if you think you know them.
- Lead with the concrete facts: who, what, how many, the outcome.
- 2 to 4 sentences, scaled to the article (hard cap ~70 words).
- Paraphrase in your own words. No verbatim sentences or phrases from the article, and no direct quotes.
- Plain text only (no markdown). No preambles like "This article is about...".

Output only the summary text, nothing else."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ro")
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--commit", action="store_true", help="actually write (default is dry-run)")
    args = ap.parse_args()

    app = create_app_for_scripts()
    with app.app_context():
        lang = Language.find(args.lang)
        articles = (
            Article.query.options(load_only(*_SAFE_COLS))
            .filter(Article.language_id == lang.id)
            .order_by(Article.published_time.desc())
            .limit(args.count)
            .all()
        )

        seen = skipped = changed = 0
        for i, a in enumerate(articles, 1):
            seen += 1
            try:
                content = a.get_content() or ""
            except Exception:
                content = a.content or ""
            content = content[:MAX_CONTENT_CHARS]
            if len(content) < 200:
                skipped += 1
                continue

            new = haiku_completion(summary_prompt(a.title, content, lang.name), max_tokens=300, temperature=0.0)
            if not new or len(new.strip()) < 20:
                skipped += 1  # LLM failed / returned junk — keep the existing summary
                continue
            new = new.strip()
            if new == (a.summary or "").strip():
                continue

            print(f"[{i}] id={a.id}")
            print(f"  OLD: {a.summary}")
            print(f"  NEW: {new}\n")

            if args.commit:
                a.summary = new
                ArticleTokenizationCache.delete_for_article(db.session, a.id)
                changed += 1
                if changed % 25 == 0:
                    db.session.commit()

        if args.commit:
            db.session.commit()
            print(f"\nCommitted {changed} updated summaries (+ invalidated their tokenization cache). "
                  f"Seen {seen}, skipped {skipped}.")
        else:
            print(f"\nDRY-RUN — nothing written. Seen {seen}, would-change shown above, skipped {skipped}. "
                  f"Re-run with --commit to apply.")


if __name__ == "__main__":
    main()
