#!/usr/bin/env python
"""
Tool to clean up markdown formatting from article summaries in the database.

Usage:
    python -m tools.cleanup_summary_formatting [--dry-run]
"""

import sys
import re
import argparse

sys.path.insert(0, "/Users/gh/zeeguu/api")

from zeeguu.api.app import create_app
from zeeguu.core.model import db
from zeeguu.core.model.article import Article


def strip_markdown_from_summary(text):
    """Remove markdown bold/italic formatting from summary text."""
    if not text:
        return text
    # Remove bold (**text** or __text__)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # Remove italic (*text* or _text_)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
    return text


def has_markdown_formatting(text):
    """Check if text contains markdown bold/italic formatting."""
    if not text:
        return False
    # Check for **bold** or __bold__
    if re.search(r'\*\*(.+?)\*\*', text) or re.search(r'__(.+?)__', text):
        return True
    # Check for *italic* or _italic_
    if re.search(r'\*(.+?)\*', text) or re.search(r'(?<!\w)_(.+?)_(?!\w)', text):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Clean up markdown formatting from article summaries")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    args = parser.parse_args()

    app = create_app()
    app.app_context().push()

    # Find articles with summaries containing markdown
    articles_with_summaries = Article.query.filter(Article.summary.isnot(None)).all()

    print(f"Found {len(articles_with_summaries)} articles with summaries")

    affected = []
    for article in articles_with_summaries:
        if has_markdown_formatting(article.summary):
            affected.append(article)

    print(f"Found {len(affected)} articles with markdown in summaries")

    if not affected:
        print("No articles need cleanup!")
        return

    for article in affected:
        original = article.summary
        cleaned = strip_markdown_from_summary(original)

        print(f"\n--- Article {article.id}: {article.title[:50]}...")
        print(f"  BEFORE: {original[:200]}...")
        print(f"  AFTER:  {cleaned[:200]}...")

        if not args.dry_run:
            article.summary = cleaned
            db.session.add(article)

    if not args.dry_run:
        db.session.commit()
        print(f"\n✓ Updated {len(affected)} article summaries")
    else:
        print(f"\n[DRY RUN] Would update {len(affected)} article summaries")


if __name__ == "__main__":
    main()
