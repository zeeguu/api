#!/usr/bin/env python
"""
Delete duplicate articles that have no user interactions.

Finds near-duplicate articles using simhash and deletes the duplicates
if they have no bookmarks, readings, or other user references.

Usage:
    python delete_duplicate_articles.py [language_code] [--delete]

    language_code: Optional. If provided, only process that language.
                   If omitted, processes all available languages.
    --delete: Optional. If provided, actually deletes duplicates.
              If omitted, runs in dry-run mode.

Examples:
    python delete_duplicate_articles.py           # Dry run for all languages
    python delete_duplicate_articles.py --delete  # Delete for all languages
    python delete_duplicate_articles.py de        # Dry run for German only
    python delete_duplicate_articles.py de --delete  # Delete German duplicates
"""

from datetime import datetime, timedelta
from simhash import Simhash
import zeeguu.core
from zeeguu.core.model import Article, Language, Bookmark, UserArticle
from zeeguu.api.app import create_app
from zeeguu.logging import logp

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session


def compute_simhash(text):
    """Compute simhash for article content."""
    if not text:
        return None
    truncated = " ".join(text.split()[:1000])
    return Simhash(truncated).value


def has_user_interactions(article):
    """Check if article has any user interactions (bookmarks, readings, etc)."""
    # Check for bookmarks via source_id
    if article.source_id:
        bookmark_count = Bookmark.query.filter_by(source_id=article.source_id).count()
        if bookmark_count > 0:
            return True

    # Check for user article interactions (reading history, likes, etc)
    user_article_count = UserArticle.query.filter_by(article_id=article.id).count()
    if user_article_count > 0:
        return True

    return False


def find_and_delete_duplicates_for_language(
    language, days_back=1, distance_threshold=5, dry_run=True
):
    """
    Find duplicate articles for a specific language and delete those without user interactions.

    Args:
        language: Language object to check articles for
        days_back: How many days back to check for duplicates
        distance_threshold: Maximum hamming distance to consider duplicates
        dry_run: If True, only report what would be deleted without actually deleting

    Returns:
        Number of duplicates found
    """
    cutoff = datetime.now() - timedelta(days=days_back)

    query = Article.query.filter(
        Article.published_time >= cutoff,
        Article.content.isnot(None),
        Article.broken == 0,
        Article.language_id == language.id,
    )

    articles = query.all()
    logp(f"Found {len(articles)} {language.name} articles to check")

    # Compute simhashes for all articles
    article_hashes = []
    for article in articles:
        simhash = compute_simhash(article.content)
        if simhash:
            article_hashes.append((article, simhash))

    logp(f"Computed {len(article_hashes)} simhashes")

    # Group articles by feed for faster comparison
    from collections import defaultdict

    by_feed = defaultdict(list)
    for article, simhash in article_hashes:
        by_feed[article.feed_id].append((article, simhash))

    logp(f"Articles spread across {len(by_feed)} feeds")

    # Find duplicates within each feed
    duplicates_to_delete = []
    seen = set()

    for feed_id, feed_articles in by_feed.items():
        logp(f"Checking feed {feed_id} ({len(feed_articles)} articles)...")

        for i, (article1, hash1) in enumerate(feed_articles):
            if article1.id in seen:
                continue

            for j, (article2, hash2) in enumerate(feed_articles):
                if i >= j or article2.id in seen:
                    continue

                distance = Simhash(hash1).distance(Simhash(hash2))

                if distance <= distance_threshold:
                    # Found a duplicate pair - decide which to keep
                    older = (
                        article1
                        if article1.published_time < article2.published_time
                        else article2
                    )
                    newer = article2 if older == article1 else article1

                    # Check which one has user interactions
                    older_has_users = has_user_interactions(older)
                    newer_has_users = has_user_interactions(newer)

                    if older_has_users and newer_has_users:
                        # Both have users, keep both
                        logp(
                            f"Both have users, keeping both: {older.id} and {newer.id}"
                        )
                        continue
                    elif older_has_users:
                        # Keep older, delete newer
                        duplicates_to_delete.append((newer, older, distance))
                        seen.add(newer.id)
                    elif newer_has_users:
                        # Keep newer, delete older
                        duplicates_to_delete.append((older, newer, distance))
                        seen.add(older.id)
                    else:
                        # Neither has users, keep newer (more likely to be better quality)
                        duplicates_to_delete.append((older, newer, distance))
                        seen.add(older.id)

    logp(f"\nFound {len(duplicates_to_delete)} duplicates to delete")

    # Report/delete duplicates
    deleted_count = 0
    for to_delete, to_keep, distance in duplicates_to_delete:
        logp(
            f"\n{'[DRY RUN] Would delete' if dry_run else 'Deleting'} article {to_delete.id}"
        )
        logp(f"  Title: {to_delete.title[:80]}")
        logp(f"  Published: {to_delete.published_time}")
        logp(f"  Keeping article {to_keep.id} (distance: {distance})")

        if not dry_run:
            db_session.delete(to_delete)
            deleted_count += 1

    if not dry_run and deleted_count > 0:
        db_session.commit()
        logp(f"\n✅ Deleted {deleted_count} duplicate {language.name} articles")
    elif dry_run:
        logp(
            f"\n[DRY RUN] Would delete {len(duplicates_to_delete)} {language.name} articles"
        )
    else:
        logp(f"\nNo {language.name} duplicates found to delete")

    return len(duplicates_to_delete)


def find_and_delete_duplicates(
    language_code=None, days_back=1, distance_threshold=5, dry_run=True
):
    """
    Find duplicate articles and delete those without user interactions.

    Args:
        language_code: Only check articles in this language (None = all languages)
        days_back: How many days back to check for duplicates
        distance_threshold: Maximum hamming distance to consider duplicates
        dry_run: If True, only report what would be deleted without actually deleting
    """

    if language_code:
        # Process single language
        language = Language.find(language_code)
        logp(f"Checking {language.name} articles from last {days_back} days...")
        find_and_delete_duplicates_for_language(
            language, days_back, distance_threshold, dry_run
        )
    else:
        # Process all languages being crawled
        logp(
            f"Checking all languages from last {days_back} days (processing each language separately)..."
        )
        languages = Language.available_languages()
        logp(f"Processing {len(languages)} languages: {[l.name for l in languages]}\n")

        total_duplicates = 0
        for language in languages:
            logp(f"\n{'='*60}")
            logp(f"Processing {language.name}...")
            logp(f"{'='*60}")
            duplicates = find_and_delete_duplicates_for_language(
                language, days_back, distance_threshold, dry_run
            )
            total_duplicates += duplicates

        logp(f"\n{'='*60}")
        logp(f"SUMMARY")
        logp(f"{'='*60}")
        logp(f"Total duplicates across all languages: {total_duplicates}")
        if dry_run:
            logp("Run with --delete flag to actually delete articles.")


if __name__ == "__main__":
    import sys

    # Parse command line arguments
    language_code = sys.argv[1] if len(sys.argv) > 1 else None
    dry_run = "--delete" not in sys.argv

    if dry_run:
        logp("Running in DRY RUN mode. Add --delete flag to actually delete articles.")

    find_and_delete_duplicates(
        language_code=language_code, days_back=10, distance_threshold=5, dry_run=dry_run
    )
