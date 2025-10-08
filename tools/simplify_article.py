#!/usr/bin/env python3
"""
Command-line tool for creating simplified versions of articles.

Usage:
    python -m tools.simplify_article <article_id> [cefr_level]
    python -m tools.simplify_article --today
    python -m tools.simplify_article --yesterday
    python -m tools.simplify_article --list <article_id>

Examples:
    python -m tools.simplify_article 123         # AI assesses level & creates all needed versions
    python -m tools.simplify_article 123 A1      # Create specific A1 version
    python -m tools.simplify_article --today     # Find today's articles and create all versions
    python -m tools.simplify_article --yesterday # Find yesterday's articles and create all versions
    python -m tools.simplify_article --list 123  # List all versions

Note: By default, AI assesses the original article's CEFR level and creates
      all simplified versions for levels simpler than the original.
      B2 article → A1, A2, B1 | C1 article → A1, A2, B1, B2 | A1 article → none
"""

import sys
import argparse
from datetime import date
from zeeguu.api.app import create_app
from zeeguu.core.model import Article, db
from zeeguu.core.llm_services.simplification_and_classification import (
    create_simplified_article_adaptive,
    simplify_and_classify,
)


app = create_app()
app.app_context().push()


def print_article_info(article):
    """Print formatted article information."""
    print(f"\nArticle ID: {article.id}")
    print(f"Title: {article.title}")
    print(f"Language: {article.language.code}")
    print(f"Word Count: {article.get_word_count()}")
    print(f"Difficulty: {article.get_fk_difficulty()}")

    if article.url:
        print(f"URL: {article.url.as_string()}")

    # Show summary for debugging
    if article.summary:
        print(f"Summary: {article.summary[:200]}...")
    else:
        print("Summary: [None]")

    if article.parent_article_id:
        print(f"CEFR Level: {article.cefr_level}")
        if (
            article.parent_article
            and hasattr(article.parent_article, "cefr_level")
            and article.parent_article.cefr_level
        ):
            print(
                f"Original CEFR Level (AI-assessed): {article.parent_article.cefr_level}"
            )
        print(f"Parent Article ID: {article.parent_article_id}")
        if article.simplification_ai_model:
            print(f"AI Model: {article.simplification_ai_model.model_name}")
    else:
        print("Type: Original Article")
        if hasattr(article, "cefr_level") and article.cefr_level:
            print(f"CEFR Level (AI-assessed): {article.cefr_level}")
        elif hasattr(article, "cefr_level") and article.cefr_level:
            print(f"CEFR Level (formula): {article.cefr_level}")
        if article.simplified_versions:
            print(f"Simplified Versions: {len(article.simplified_versions)}")
            for simplified in article.simplified_versions:
                level_info = f"{simplified.cefr_level}"
                if hasattr(article, "cefr_level") and article.cefr_level:
                    level_info += f" (from {article.cefr_level})"
                elif hasattr(article, "cefr_level") and article.cefr_level:
                    level_info += f" (from {article.cefr_level})"
                print(f"  - {level_info} (ID: {simplified.id})")


def list_article_versions(article_id):
    """List all versions of an article."""
    print(f"Listing all versions for article {article_id}...")

    article = Article.find_by_id(article_id)
    if not article:
        print(f"❌ Article {article_id} not found")
        return False

    # If this is a simplified version, get the parent
    if article.parent_article_id:
        original_article = Article.find_by_id(article.parent_article_id)
        print("🔍 This is a simplified version. Showing parent article:")
        print_article_info(original_article)
    else:
        original_article = article
        print("📄 Original Article:")
        print_article_info(original_article)

    # Show all simplified versions
    if original_article.simplified_versions:
        print(
            f"\n📝 Simplified Versions ({len(original_article.simplified_versions)}):"
        )
        for simplified in original_article.simplified_versions:
            print(f"\n{simplified.cefr_level} Version:")
            print_article_info(simplified)
    else:
        print("\n📝 No simplified versions found")

    return True


def simplify_single_article(article_id, cefr_level):
    """Create a single simplified version of an article."""
    print(f"Creating {cefr_level} simplified version for article {article_id}...")

    # Validate CEFR level
    valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    if cefr_level not in valid_levels:
        print(f"❌ Invalid CEFR level: {cefr_level}")
        print(f"Valid levels: {', '.join(valid_levels)}")
        return False

    # Find the original article
    article = Article.find_by_id(article_id)
    if not article:
        print(f"❌ Article {article_id} not found")
        return False

    # Don't simplify already simplified articles
    if article.parent_article_id:
        print(f"❌ Article {article_id} is already a simplified version")
        print("Use the parent article ID instead")
        return False

    print(f"\n📄 Original Article:")
    print_article_info(article)

    # Check if this level already exists
    for existing in article.simplified_versions:
        if existing.cefr_level == cefr_level:
            print(f"\n⚠️  {cefr_level} version already exists (ID: {existing.id})")
            return True

    try:
        print(f"\n🤖 Generating {cefr_level} simplified version using AI...")
        simplified_article = create_simplified_article_adaptive(
            db.session, article, cefr_level
        )

        print(f"\n✅ Successfully created {cefr_level} simplified version!")
        # Refresh the article to ensure we have the latest state
        db.session.refresh(simplified_article)
        print_article_info(simplified_article)
        return True

    except Exception as e:
        print(f"\n❌ Simplification failed: {str(e)}")
        return False


def simplify_all_levels(article_id):
    """Create simplified versions for all levels based on LLM assessment of original article."""
    print(f"Creating adaptive simplified versions for article {article_id}...")

    # Find the original article
    article = Article.find_by_id(article_id)
    if not article:
        print(f"❌ Article {article_id} not found")
        return False

    # Don't simplify already simplified articles
    if article.parent_article_id:
        print(f"❌ Article {article_id} is already a simplified version")
        print("Use the parent article ID instead")
        return False

    print(f"\n📄 Original Article:")
    print_article_info(article)

    try:
        print(
            f"\n🤖 Using AI to assess original level and create all appropriate simplified versions..."
        )
        simplified_articles, classifications = simplify_and_classify(db.session, article)

        if not simplified_articles:
            print(f"\n⚠️  No simplified versions created for article {article.id}")
            print(
                f"💡 Check the logs above for the specific reason (SKIP: or ERROR: messages)"
            )
            print(f"📊 Article info:")
            print(f"   - Word count: {article.get_word_count()}")
            print(f"   - Language: {article.language.code}")
            print(f"   - Has parent: {bool(article.parent_article_id)}")
            print(
                f"   - Existing simplified versions: {len(article.simplified_versions)}"
            )
            if article.simplified_versions:
                levels = [v.cefr_level for v in article.simplified_versions]
                print(f"     Levels: {levels}")
            return True

        print(
            f"\n✅ Successfully created {len(simplified_articles)} simplified versions!"
        )

        # Show the assessed original level
        if article.cefr_level:
            print(f"\n📊 AI Assessment: Original article is {article.cefr_level} level")

        # Show each created version
        for simplified in simplified_articles:
            print(f"\n{simplified.cefr_level} Version:")
            # Refresh the article to ensure we have the latest state
            db.session.refresh(simplified)
            print_article_info(simplified)

        return True

    except Exception as e:
        print(f"\n❌ Adaptive simplification failed: {str(e)}")
        if "incomplete due to paywall" in str(e):
            print("💡 This article appears to be truncated by a paywall.")
        return False


def simplify_articles_by_date(target_date, date_name):
    """Find all articles from a specific date and create simplified versions for them."""
    from datetime import datetime, timedelta
    
    print(f"🔍 Finding articles from {date_name} ({target_date})...")
    
    # Create datetime objects for start and end of the target date
    start_of_date = datetime.combine(target_date, datetime.min.time())
    end_of_date = start_of_date + timedelta(days=1)
    
    # Find articles published on the target date
    articles = Article.query.filter(
        Article.published_time >= start_of_date,
        Article.published_time < end_of_date,
        Article.parent_article_id == None,  # Only original articles
        Article.broken == 0  # Not broken
    ).all()
    
    if not articles:
        print(f"📭 No articles found from {date_name} ({target_date})")
        return True
    
    print(f"📰 Found {len(articles)} articles from {date_name}")
    
    total_success = 0
    total_failed = 0
    
    for i, article in enumerate(articles, 1):
        print(f"\n📄 Processing article {i}/{len(articles)} (ID: {article.id})")
        print(f"Title: {article.title}")
        
        # Check if it already has simplified versions
        if article.simplified_versions:
            print(f"⚠️  Article {article.id} already has {len(article.simplified_versions)} simplified versions")
            continue
        
        try:
            simplified_articles, classifications = simplify_and_classify(db.session, article)
            if simplified_articles:
                print(f"✅ Created {len(simplified_articles)} simplified versions for article {article.id}")
                total_success += 1
            else:
                print(f"⚠️  No simplified versions created for article {article.id}")
        except Exception as e:
            print(f"❌ Failed to simplify article {article.id}: {str(e)}")
            total_failed += 1
    
    print(f"\n📊 Summary:")
    print(f"  ✅ Successfully simplified: {total_success} articles")
    print(f"  ❌ Failed to simplify: {total_failed} articles")
    print(f"  ⚠️  Skipped (already had versions): {len(articles) - total_success - total_failed} articles")
    
    return total_failed == 0


def simplify_today_articles():
    """Find all articles from today and create simplified versions for them."""
    from datetime import timedelta
    
    today = date.today()
    return simplify_articles_by_date(today, "today")


def simplify_yesterday_articles():
    """Find all articles from yesterday and create simplified versions for them."""
    from datetime import timedelta
    
    yesterday = date.today() - timedelta(days=1)
    return simplify_articles_by_date(yesterday, "yesterday")


def main():
    parser = argparse.ArgumentParser(
        description="Create simplified versions of articles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.simplify_article 123         # AI creates all needed versions
  python -m tools.simplify_article 123 A1      # Create specific A1 version
  python -m tools.simplify_article --today     # Find today's articles and create all versions
  python -m tools.simplify_article --yesterday # Find yesterday's articles and create all versions
  python -m tools.simplify_article --list 123  # List all versions

Note: By default, AI assesses the original CEFR level and creates all 
      simplified versions for levels simpler than the original.
        """,
    )

    parser.add_argument("article_id", nargs="?", type=int, help="ID of the article to simplify")
    parser.add_argument(
        "cefr_level", nargs="?", help="CEFR level (A1, A2, B1, B2, C1, C2)"
    )
    parser.add_argument(
        "--today",
        action="store_true",
        help="Find articles from today and create all simplified versions",
    )
    parser.add_argument(
        "--yesterday",
        action="store_true",
        help="Find articles from yesterday and create all simplified versions",
    )
    parser.add_argument(
        "--list", action="store_true", help="List all versions of the article"
    )

    args = parser.parse_args()

    # Handle today command
    if args.today:
        success = simplify_today_articles()
        sys.exit(0 if success else 1)

    # Handle yesterday command
    if args.yesterday:
        success = simplify_yesterday_articles()
        sys.exit(0 if success else 1)

    # Handle list command
    if args.list:
        if not args.article_id:
            print("❌ Please specify an article ID with --list")
            parser.print_help()
            sys.exit(1)
        success = list_article_versions(args.article_id)
        sys.exit(0 if success else 1)

    # Handle simplification commands
    if not args.article_id:
        print("❌ Please specify an article ID or use --today/--yesterday")
        parser.print_help()
        sys.exit(1)

    if args.cefr_level:
        success = simplify_single_article(args.article_id, args.cefr_level.upper())
    else:
        # Default behavior: create all versions (was --all)
        success = simplify_all_levels(args.article_id)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
