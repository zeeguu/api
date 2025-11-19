#!/usr/bin/env python
"""
Delete an article by URL.

Usage:
    python tools/delete_article_by_url.py "https://example.com/article"
"""

import sys
from zeeguu.api.app import create_app
from zeeguu.core.model import db, Article, Url

app = create_app()
app.app_context().push()


def delete_article_by_url(url_string, force=False):
    """Delete an article and its associated data by URL."""

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

    print(f"Found article:")
    print(f"  ID: {article.id}")
    print(f"  Title: {article.title}")
    print(f"  Language: {article.language.name}")
    print(f"  URL: {canonical_url}")

    # Check for related data
    from zeeguu.core.model import UserArticle, ArticleFragment
    user_articles = UserArticle.query.filter_by(article_id=article.id).count()
    fragments = ArticleFragment.query.filter_by(article_id=article.id).count()

    print(f"\nRelated data:")
    print(f"  UserArticles: {user_articles}")
    print(f"  ArticleFragments: {fragments}")

    # Ask for confirmation
    if not force:
        response = input("\nDelete this article and all related data? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return False

    # Delete related data first (in correct order to avoid FK violations)
    print("\nDeleting related data...")

    # Delete user articles
    deleted = UserArticle.query.filter_by(article_id=article.id).delete()
    print(f"  Deleted {deleted} UserArticle records")

    # Delete article fragments
    deleted = ArticleFragment.query.filter_by(article_id=article.id).delete()
    print(f"  Deleted {deleted} ArticleFragment records")

    # Now delete the article
    db.session.delete(article)
    db.session.commit()

    print(f"✅ Article deleted successfully!")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/delete_article_by_url.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    delete_article_by_url(url)
