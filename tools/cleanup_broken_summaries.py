#!/usr/bin/env python
"""
Tool to detect and clean up broken article summaries (HTML junk, navigation elements).

Articles with broken summaries can either:
1. Have their summary cleared (set to None)
2. Be marked as broken if they have no user interactions
3. Be deleted if they have no user interactions (with --delete flag)

Usage:
    python -m tools.cleanup_broken_summaries [--dry-run] [--delete]
"""

import sys
import re
import argparse

sys.path.insert(0, "/Users/gh/zeeguu/api")

from zeeguu.api.app import create_app
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache


def has_html_junk(text):
    """Check if summary contains HTML tags that indicate broken parsing."""
    if not text:
        return False

    # Patterns that indicate broken/junk summaries
    junk_patterns = [
        r'<div\s+class=',          # HTML div with class
        r'<figure>',               # figure tags
        r'<img\s',                 # img tags
        r'<a\s+href=',             # links
        r'field-name-field',       # Drupal field junk
        r'feedflare',              # RSS feed junk
        r'class="field',           # HTML class attributes
        r'<h[1-6]>',               # Header tags in summary
        r'<p>',                    # Paragraph tags
        r'<em>',                   # Emphasis tags
        r'</div>',                 # Closing divs
        r'src="http',              # Image sources
    ]

    for pattern in junk_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def has_navigation_junk(text):
    """Check if summary contains navigation/UI junk text."""
    if not text:
        return False

    # Text patterns that indicate navigation or UI elements
    junk_texts = [
        'cookie',
        'subscribe',
        'sign up',
        'log in',
        'read more',
        'click here',
        'javascript',
        'advertisement',
        'skip to content',
        'menu',
        'search',
        'share this',
        'follow us',
    ]

    text_lower = text.lower()
    # Only flag if these appear at the start (first 100 chars) suggesting it's junk
    start_text = text_lower[:100]
    for junk in junk_texts:
        if junk in start_text:
            return True
    return False


def article_has_interactions(article_id):
    """Check if article has any user interactions (user_article entries)."""
    # Check for user_article entries - this is the main indicator of user interaction
    user_article_count = UserArticle.query.filter_by(article_id=article_id).count()
    return user_article_count > 0


def main():
    parser = argparse.ArgumentParser(description="Clean up broken article summaries")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    parser.add_argument("--delete", action="store_true", help="Delete articles with no interactions instead of just clearing summary")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of articles to process")
    args = parser.parse_args()

    app = create_app()
    app.app_context().push()

    # Find articles with summaries
    query = Article.query.filter(Article.summary.isnot(None))
    if args.limit:
        query = query.limit(args.limit)

    articles_with_summaries = query.all()
    print(f"Checking {len(articles_with_summaries)} articles with summaries...")

    broken_html = []
    broken_nav = []

    for article in articles_with_summaries:
        if has_html_junk(article.summary):
            broken_html.append(article)
        elif has_navigation_junk(article.summary):
            broken_nav.append(article)

    print(f"\nFound {len(broken_html)} articles with HTML junk in summaries")
    print(f"Found {len(broken_nav)} articles with navigation junk in summaries")

    all_broken = broken_html + broken_nav

    if not all_broken:
        print("No broken summaries found!")
        return

    # Categorize by whether they have interactions
    with_interactions = []
    without_interactions = []

    for article in all_broken:
        if article_has_interactions(article.id):
            with_interactions.append(article)
        else:
            without_interactions.append(article)

    print(f"\n  - {len(with_interactions)} have user interactions (will clear summary only)")
    print(f"  - {len(without_interactions)} have NO interactions", end="")
    if args.delete:
        print(" (will DELETE)")
    else:
        print(" (will clear summary)")

    # Process articles with interactions - just clear summary
    cleared_count = 0
    for article in with_interactions:
        print(f"\n--- Article {article.id}: {article.title[:50]}...")
        print(f"  Summary (broken): {article.summary[:100]}...")
        print(f"  Action: Clear summary (has interactions)")

        if not args.dry_run:
            article.summary = None
            db.session.add(article)

            # Invalidate tokenization cache
            cache = ArticleTokenizationCache.get_for_article(db.session, article.id)
            if cache and cache.tokenized_summary:
                cache.tokenized_summary = None
                db.session.add(cache)

            cleared_count += 1

    # Process articles without interactions
    deleted_count = 0
    for article in without_interactions:
        print(f"\n--- Article {article.id}: {article.title[:50]}...")
        print(f"  Summary (broken): {article.summary[:100]}...")

        if args.delete:
            print(f"  Action: DELETE (no interactions)")
            if not args.dry_run:
                db.session.delete(article)
                deleted_count += 1
        else:
            print(f"  Action: Clear summary (no interactions)")
            if not args.dry_run:
                article.summary = None
                db.session.add(article)

                cache = ArticleTokenizationCache.get_for_article(db.session, article.id)
                if cache and cache.tokenized_summary:
                    cache.tokenized_summary = None
                    db.session.add(cache)

                cleared_count += 1

    if not args.dry_run:
        db.session.commit()
        print(f"\n✓ Cleared {cleared_count} summaries")
        if args.delete:
            print(f"✓ Deleted {deleted_count} articles")
    else:
        print(f"\n[DRY RUN] Would clear {len(with_interactions) + (0 if args.delete else len(without_interactions))} summaries")
        if args.delete:
            print(f"[DRY RUN] Would delete {len(without_interactions)} articles")


if __name__ == "__main__":
    main()
