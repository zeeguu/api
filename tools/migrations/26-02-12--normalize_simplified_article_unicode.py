"""
Migration: Normalize Unicode in simplified articles

This script fixes articles that were created with LLM-generated content
containing decomposed Unicode characters (NFD). It normalizes them to
composed form (NFC) to fix visual rendering issues with diacritics.

Run with: source ~/.venvs/z_env/bin/activate && python -m tools.migrations.26-02-12--normalize_simplified_article_unicode

Options:
  --language ro     Only process Romanian articles
  --today           Only process articles from today
  --dry-run         Show what would be fixed without making changes
"""

import argparse
import unicodedata
from datetime import datetime, timedelta
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.core.model.source import Source


def normalize_nfc(text):
    """Normalize text to NFC (composed Unicode form)"""
    if text is None:
        return None
    return unicodedata.normalize("NFC", text)


def has_decomposed_chars(text):
    """Check if text contains decomposed Unicode characters"""
    if text is None:
        return False
    return text != unicodedata.normalize("NFC", text)


def migrate(language_code=None, today_only=False, dry_run=False):
    session = db.session

    # Build query for simplified articles
    query = session.query(Article).filter(Article.parent_article_id.isnot(None))

    # Filter by language if specified
    if language_code:
        lang = Language.find(language_code)
        if not lang:
            print(f"Language '{language_code}' not found!")
            return
        query = query.filter(Article.language_id == lang.id)
        print(f"Filtering by language: {lang.name}")

    # Filter by today if specified
    if today_only:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Article.published_time >= today_start)
        print(f"Filtering by date: {today_start.date()}")

    simplified_articles = query.all()
    print(f"Found {len(simplified_articles)} simplified articles to check")

    if dry_run:
        print("DRY RUN - no changes will be made")

    fixed_count = 0
    for article in simplified_articles:
        needs_fix = False

        # Check and fix title
        if has_decomposed_chars(article.title):
            print(f"  Article {article.id}: Fixing title")
            if not dry_run:
                article.title = normalize_nfc(article.title)
            needs_fix = True

        # Check and fix summary
        if has_decomposed_chars(article.summary):
            print(f"  Article {article.id}: Fixing summary")
            if not dry_run:
                article.summary = normalize_nfc(article.summary)
            needs_fix = True

        # Check and fix source content (via source_text)
        if article.source_id:
            source = session.query(Source).get(article.source_id)
            if source and source.source_text and has_decomposed_chars(source.source_text.content):
                print(f"  Article {article.id}: Fixing source content")
                if not dry_run:
                    source.source_text.content = normalize_nfc(source.source_text.content)
                needs_fix = True

        # Check and fix HTML content
        if has_decomposed_chars(article.htmlContent):
            print(f"  Article {article.id}: Fixing HTML content")
            if not dry_run:
                article.htmlContent = normalize_nfc(article.htmlContent)
            needs_fix = True

        if needs_fix:
            fixed_count += 1
            if not dry_run:
                session.add(article)

    if fixed_count > 0:
        if dry_run:
            print(f"\nWould fix {fixed_count} articles.")
        else:
            print(f"\nFixing {fixed_count} articles...")
            session.commit()
            print("Done!")
    else:
        print("\nNo articles needed fixing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normalize Unicode in simplified articles")
    parser.add_argument("--language", "-l", help="Language code (e.g., 'ro' for Romanian)")
    parser.add_argument("--today", action="store_true", help="Only process articles from today")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed without making changes")
    args = parser.parse_args()

    from zeeguu.api.app import create_app

    app = create_app()
    with app.app_context():
        migrate(language_code=args.language, today_only=args.today, dry_run=args.dry_run)
