"""
Migration: Normalize Unicode in simplified articles

This script fixes articles that were created with LLM-generated content
containing decomposed Unicode characters (NFD). It normalizes them to
composed form (NFC) to fix visual rendering issues with diacritics.

Run with: source ~/.venvs/z_env/bin/activate && python -m tools.migrations.26-02-12--normalize_simplified_article_unicode
"""

import unicodedata
from zeeguu.core.model import db
from zeeguu.core.model.article import Article
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


def migrate():
    session = db.session

    # Find all simplified articles (those with parent_article_id set)
    simplified_articles = (
        session.query(Article).filter(Article.parent_article_id.isnot(None)).all()
    )

    print(f"Found {len(simplified_articles)} simplified articles to check")

    fixed_count = 0
    for article in simplified_articles:
        needs_fix = False

        # Check and fix title
        if has_decomposed_chars(article.title):
            print(f"  Article {article.id}: Fixing title")
            article.title = normalize_nfc(article.title)
            needs_fix = True

        # Check and fix summary
        if has_decomposed_chars(article.summary):
            print(f"  Article {article.id}: Fixing summary")
            article.summary = normalize_nfc(article.summary)
            needs_fix = True

        # Check and fix source content
        if article.source_id:
            source = session.query(Source).get(article.source_id)
            if source and has_decomposed_chars(source.content):
                print(f"  Article {article.id}: Fixing source content")
                source.content = normalize_nfc(source.content)
                needs_fix = True

        # Check and fix HTML content
        if has_decomposed_chars(article.htmlContent):
            print(f"  Article {article.id}: Fixing HTML content")
            article.htmlContent = normalize_nfc(article.htmlContent)
            needs_fix = True

        if needs_fix:
            fixed_count += 1
            session.add(article)

    if fixed_count > 0:
        print(f"\nFixing {fixed_count} articles...")
        session.commit()
        print("Done!")
    else:
        print("\nNo articles needed fixing.")


if __name__ == "__main__":
    from zeeguu.api.app import create_app

    app = create_app()
    with app.app_context():
        migrate()
