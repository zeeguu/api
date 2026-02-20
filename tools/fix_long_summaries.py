#!/usr/bin/env python3
"""
Fix long summaries in Danish articles from the past few days.

The prompt was recently updated to ensure summaries are max 25 words,
but some existing articles have longer summaries that need to be shortened.

Usage:
    python -m tools.fix_long_summaries           # Dry run - show what would be fixed
    python -m tools.fix_long_summaries --fix     # Actually fix the summaries
    python -m tools.fix_long_summaries --days 5  # Check last 5 days instead of default 3
"""

import sys
import os
import argparse
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language

app = create_app()
app.app_context().push()

MAX_SUMMARY_WORDS = 25


def count_words(text):
    """Count words in a text."""
    if not text:
        return 0
    return len(text.split())


def shorten_summary_with_llm(summary, title, language_code):
    """
    Use LLM to shorten a summary to max 25 words.

    Args:
        summary: The current (too long) summary
        title: The article title (for context)
        language_code: Language code (e.g., 'da')

    Returns:
        Shortened summary or None if failed
    """
    language_name = Language.LANGUAGE_NAMES.get(language_code, language_code)

    prompt = f"""You are a {language_name} language editor. Your task is to shorten the following summary to a maximum of 25 words while preserving the key meaning.

RULES:
- Output ONLY the shortened summary in {language_name}
- Maximum 25 words
- Plain text only - NO markdown formatting (no bold, no italic, no special characters)
- Keep the essential information
- The summary should complement the title, not repeat it

Title: {title}

Current summary (too long): {summary}

Shortened summary (max 25 words):"""

    api_key = os.environ.get("ANTHROPIC_TEXT_SIMPLIFICATION_KEY")
    if not api_key:
        print("  ERROR: ANTHROPIC_TEXT_SIMPLIFICATION_KEY not set")
        return None

    try:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        data = {
            "model": "claude-3-haiku-20240307",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.1,
        }

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            timeout=30,
        )

        if response.status_code != 200:
            print(f"  ERROR: API error {response.status_code}: {response.text[:200]}")
            return None

        result = response.json()["content"][0]["text"].strip()

        # Validate the result
        word_count = count_words(result)
        if word_count > MAX_SUMMARY_WORDS:
            print(f"  WARNING: LLM returned {word_count} words, still too long")
            # Try to truncate intelligently
            words = result.split()[:MAX_SUMMARY_WORDS]
            result = " ".join(words)
            if not result.endswith("."):
                result += "."

        return result

    except Exception as e:
        print(f"  ERROR: Failed to call LLM: {e}")
        return None


def find_long_summaries(language_code, days_back=3):
    """
    Find articles with summaries longer than MAX_SUMMARY_WORDS.

    Args:
        language_code: Language code to filter by (e.g., 'da')
        days_back: Number of days to look back

    Returns:
        List of articles with long summaries
    """
    language = Language.find(language_code)
    if not language:
        print(f"Language '{language_code}' not found")
        return []

    cutoff_date = datetime.now() - timedelta(days=days_back)

    # Find articles with summaries
    articles = Article.query.filter(
        Article.language_id == language.id,
        Article.published_time >= cutoff_date,
        Article.summary != None,
        Article.summary != "",
        Article.broken == 0,
    ).all()

    # Filter to those with long summaries
    long_summary_articles = []
    for article in articles:
        word_count = count_words(article.summary)
        if word_count > MAX_SUMMARY_WORDS:
            long_summary_articles.append((article, word_count))

    return long_summary_articles


def fix_summaries(language_code="da", days_back=3, dry_run=True):
    """
    Find and fix long summaries in articles.

    Args:
        language_code: Language to process
        days_back: Number of days to look back
        dry_run: If True, only show what would be fixed without making changes
    """
    print(f"{'DRY RUN - ' if dry_run else ''}Fixing long summaries for {language_code} articles")
    print(f"Looking back {days_back} days, max summary length: {MAX_SUMMARY_WORDS} words")
    print()

    articles = find_long_summaries(language_code, days_back)

    if not articles:
        print("No articles with long summaries found!")
        return

    print(f"Found {len(articles)} articles with summaries > {MAX_SUMMARY_WORDS} words:")
    print()

    fixed_count = 0
    failed_count = 0

    for article, word_count in articles:
        print(f"Article {article.id}: {article.title[:60]}...")
        print(f"  Current summary ({word_count} words): {article.summary[:100]}...")

        if dry_run:
            print(f"  [DRY RUN] Would shorten this summary")
            print()
            continue

        # Actually fix the summary
        new_summary = shorten_summary_with_llm(
            article.summary,
            article.title,
            language_code
        )

        if new_summary:
            new_word_count = count_words(new_summary)
            print(f"  New summary ({new_word_count} words): {new_summary}")

            # Update the article
            article.summary = new_summary
            db.session.add(article)
            db.session.commit()
            print(f"  FIXED!")
            fixed_count += 1
        else:
            print(f"  FAILED to generate new summary")
            failed_count += 1

        print()

    print("=" * 60)
    print(f"Summary:")
    print(f"  Total articles with long summaries: {len(articles)}")
    if not dry_run:
        print(f"  Fixed: {fixed_count}")
        print(f"  Failed: {failed_count}")
    else:
        print(f"  Run with --fix to actually fix these summaries")


def main():
    parser = argparse.ArgumentParser(
        description="Fix long summaries in Danish articles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Actually fix the summaries (without this flag, only shows what would be fixed)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Number of days to look back (default: 3)",
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="da",
        help="Language code (default: da for Danish)",
    )

    args = parser.parse_args()

    fix_summaries(
        language_code=args.lang,
        days_back=args.days,
        dry_run=not args.fix,
    )


if __name__ == "__main__":
    main()
