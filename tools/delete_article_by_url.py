#!/usr/bin/env python
"""
Delete an article by URL or ID.

Usage:
    python tools/delete_article_by_url.py "https://example.com/article"
    python tools/delete_article_by_url.py --id 12345
"""

import sys
from zeeguu.api.app import create_app
from zeeguu.core.model import db, Article, Url

app = create_app()
app.app_context().push()


def delete_article_by_url(url_string, force=False):
    """Delete an article and its associated data by URL."""

    try:
        # Find the URL
        canonical_url = Url.extract_canonical_url(url_string)
        url_obj = Url.find(canonical_url)

        if not url_obj:
            print(f"❌ URL not found: {canonical_url}")
            return False

        # Find the article
        article = Article.query.filter_by(url_id=url_obj.id).first()

        if not article:
            print(f"❌ Article not found for URL: {canonical_url}")
            return False
    except Exception as e:
        print(f"❌ Error finding article: {e}")
        return False

    return delete_article(article, force)


def delete_article_by_id(article_id, force=False):
    """Delete an article by ID."""
    article = Article.query.get(article_id)

    if not article:
        print(f"❌ Article not found with ID: {article_id}")
        return False

    return delete_article(article, force)


def delete_article(article, force=False):
    """Common deletion logic for both URL and ID."""
    print(f"Found article:")
    print(f"  ID: {article.id}")
    print(f"  Title: {article.title}")
    print(f"  Language: {article.language.name}")

    # Check for related data
    from zeeguu.core.model import UserArticle, ArticleFragment, UserReadingSession
    user_articles = UserArticle.query.filter_by(article_id=article.id).count()
    fragments = ArticleFragment.query.filter_by(article_id=article.id).count()
    sessions = UserReadingSession.query.filter_by(article_id=article.id).count()

    print(f"\nRelated data:")
    print(f"  UserReadingSessions: {sessions}")
    print(f"  UserArticles: {user_articles}")
    print(f"  ArticleFragments: {fragments}")

    # Ask for confirmation
    if not force:
        response = input("\nDelete this article and all related data? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return False

    # Delete related data first
    print("\nDeleting related data...")

    deleted = UserReadingSession.query.filter_by(article_id=article.id).delete()
    print(f"  Deleted {deleted} UserReadingSession records")

    deleted = UserArticle.query.filter_by(article_id=article.id).delete()
    print(f"  Deleted {deleted} UserArticle records")

    deleted = ArticleFragment.query.filter_by(article_id=article.id).delete()
    print(f"  Deleted {deleted} ArticleFragment records")

    # Delete article
    db.session.delete(article)
    db.session.commit()

    print(f"✅ Article deleted successfully!")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python tools/delete_article_by_url.py <url>")
        print("  python tools/delete_article_by_url.py --id <article_id>")
        sys.exit(1)

    if sys.argv[1] == '--id':
        if len(sys.argv) != 3:
            print("Error: --id requires an article ID")
            sys.exit(1)
        article_id = int(sys.argv[2])
        delete_article_by_id(article_id)
    else:
        url = sys.argv[1]
        delete_article_by_url(url)
