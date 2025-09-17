#!/usr/bin/env python
"""
Test script for classroom/cohort recommendations for a given user.

This script tests the recommendation system for users who are part of a classroom (cohort).
It shows what articles are recommended based on:
- User's language preferences
- User's difficulty level
- Cohort's assigned articles
- User's subscribed topics
- User's search preferences
"""

import argparse
import os
import sys

# Add parent directory to path to import zeeguu modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from zeeguu.core.model import User, Cohort, CohortArticleMap, UserCohortMap
from zeeguu.core.content_recommender.elastic_recommender import (
    article_recommendations_for_user,
    video_recommendations_for_user,
    _prepare_user_constraints,
)
from zeeguu.api.app import create_app


def print_separator(title=""):
    """Print a visual separator with optional title."""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print("=" * 60)
    else:
        print("-" * 60)


def get_user_cohorts(user):
    """Get all cohorts a user belongs to."""
    cohorts = []

    # Check UserCohortMap
    user_cohort_maps = UserCohortMap.query.filter_by(user_id=user.id).all()
    for ucm in user_cohort_maps:
        cohorts.append(ucm.cohort)

    # Also check by invitation code (backwards compatibility)
    if user.invitation_code:
        cohort_by_code = Cohort.query.filter_by(inv_code=user.invitation_code).first()
        if cohort_by_code and cohort_by_code not in cohorts:
            cohorts.append(cohort_by_code)

    return cohorts


def test_user_recommendations(user_email, show_details=True, count=20):
    """Test recommendations for a specific user."""

    app = create_app()
    app.app_context().push()

    try:
        user = User.find(user_email)
    except Exception as e:
        print(f"Error: Could not find user with email '{user_email}'")
        return

    print_separator(f"Testing Recommendations for User: {user.name}")
    print(f"Email: {user.email}")
    print(f"ID: {user.id}")
    print(
        f"Learned Language: {user.learned_language.name if user.learned_language else 'None'} (ID: {user.learned_language_id})"
    )

    # Show user's cohorts
    print_separator("User's Cohorts/Classrooms")
    cohorts = get_user_cohorts(user)
    if cohorts:
        for cohort in cohorts:
            print(f"\n  Cohort: {cohort.name} (ID: {cohort.id})")
            print(f"    Invitation Code: {cohort.inv_code}")
            print(
                f"    Language: {cohort.language.name if cohort.language else 'None'} (ID: {cohort.language_id})"
            )
            print(
                f"    Students: {cohort.get_current_student_count()}/{cohort.max_students}"
            )
            
            # Check language match
            if cohort.language_id != user.learned_language_id:
                print(f"    ⚠️  WARNING: Cohort language ({cohort.language_id}) doesn't match user's learned language ({user.learned_language_id})!")
                print(f"       Articles from this cohort won't appear in the Classroom tab")

            # Show cohort's assigned articles
            cohort_articles = CohortArticleMap.get_articles_info_for_cohort(cohort)
            if cohort_articles:
                print(f"    Assigned Articles: {len(cohort_articles)} articles")
                if show_details:
                    for i, article_info in enumerate(cohort_articles[:5], 1):
                        title = article_info.get("title", "Untitled")
                        print(f"      {i}. {title[:60]}...")
                    if len(cohort_articles) > 5:
                        print(f"      ... and {len(cohort_articles) - 5} more")
    else:
        print("  User is not part of any cohort")

    # Show user preferences
    print_separator("User Preferences & Constraints")

    # Get user constraints for recommendations
    (
        language,
        upper_bounds,
        lower_bounds,
        topics_to_include,
        topics_to_exclude,
        wanted_searches,
        unwanted_searches,
        ignored_sources,
    ) = _prepare_user_constraints(user)

    print(f"  Language: {language.name if language else 'Not set'}")
    print(f"  Difficulty Level: {lower_bounds/10:.1f} - {upper_bounds/10:.1f}")

    # Topics
    print(f"\n  Subscribed Topics:")
    if topics_to_include:
        for topic in topics_to_include.split(","):
            if topic:
                print(f"    + {topic}")
    else:
        print("    (none)")

    print(f"\n  Excluded Topics:")
    if topics_to_exclude:
        for topic in topics_to_exclude.split(","):
            if topic:
                print(f"    - {topic}")
    else:
        print("    (none)")

    # Searches
    print(f"\n  Saved Searches:")
    if wanted_searches:
        for search in wanted_searches.split():
            print(f"    + {search}")
    else:
        print("    (none)")

    print(f"\n  Excluded Searches:")
    if unwanted_searches:
        for search in unwanted_searches.split():
            print(f"    - {search}")
    else:
        print("    (none)")

    # Ignored sources
    if ignored_sources:
        print(f"\n  Ignored Sources: {', '.join(ignored_sources)}")
    
    # Test cohort articles endpoint
    print_separator("Cohort Articles (Classroom Tab)")
    
    # First show what the frontend sees
    print("Frontend checks:")
    print(f"  - User has {len(cohorts)} cohort(s)")
    print(f"  - studentJoinedCohort would be: {len(cohorts) > 0}")
    
    try:
        cohort_articles = user.cohort_articles_for_user()
        if cohort_articles:
            print(f"\nFound {len(cohort_articles)} articles in Classroom tab:\n")
            for i, article_info in enumerate(cohort_articles[:5], 1):
                title = article_info.get("title", "Untitled")
                print(f"{i:2}. {title[:70]}...")
                if show_details:
                    difficulty = article_info.get("metrics", {}).get("difficulty", "Unknown")
                    print(f"     Difficulty: {difficulty}")
            if len(cohort_articles) > 5:
                print(f"\n     ... and {len(cohort_articles) - 5} more")
        else:
            print("\n⚠️  No articles found in Classroom tab!")
            print("\nDiagnosis:")
            
            # Check each cohort
            for cohort in cohorts:
                cohort_articles_raw = CohortArticleMap.get_articles_info_for_cohort(cohort)
                print(f"\n  Cohort: {cohort.name}")
                print(f"    - Has {len(cohort_articles_raw)} assigned articles")
                print(f"    - Cohort language ID: {cohort.language_id}")
                print(f"    - User learned language ID: {user.learned_language_id}")
                if cohort.language_id != user.learned_language_id:
                    print(f"    ❌ Language mismatch - articles won't show!")
                else:
                    print(f"    ✅ Language matches")
            
            print("\nTo fix: Either change user's learned language or cohort's language to match.")
    except Exception as e:
        print(f"Error getting cohort articles: {e}")
        import traceback
        traceback.print_exc()

    # Get article recommendations
    print_separator("Article Recommendations")
    try:
        articles = article_recommendations_for_user(user, count=count)

        if articles:
            print(f"Found {len(articles)} recommended articles:\n")
            for i, article in enumerate(articles, 1):
                print(f"{i:2}. {article.title[:70]}...")
                if show_details:
                    print(
                        f"     Published: {article.published_time.strftime('%Y-%m-%d %H:%M') if article.published_time else 'Unknown'}"
                    )
                    print(
                        f"     Language: {article.language.name if article.language else 'Unknown'}"
                    )
                    if hasattr(article, "fk_difficulty"):
                        print(f"     Difficulty: {article.fk_difficulty}")
                    topics = article.topics if hasattr(article, "topics") else []
                    if topics:
                        topic_names = (
                            [t.title for t in topics]
                            if hasattr(topics[0], "title")
                            else []
                        )
                        if topic_names:
                            print(f"     Topics: {', '.join(topic_names[:3])}")

                    # Check if article is from cohort
                    for cohort in cohorts:
                        if CohortArticleMap.find(cohort.id, article.id):
                            print(f"     ⚡ From Cohort: {cohort.name}")
                    print()
        else:
            print("No article recommendations found for this user.")
    except Exception as e:
        print(f"Error getting article recommendations: {e}")
        import traceback

        traceback.print_exc()

    # Get video recommendations (if available)
    print_separator("Video Recommendations")
    try:
        videos = video_recommendations_for_user(user, count=10)

        if videos:
            print(f"Found {len(videos)} recommended videos:\n")
            for i, video in enumerate(videos, 1):
                print(f"{i:2}. {video.title[:70]}...")
                if show_details:
                    print(
                        f"     Duration: {video.duration if hasattr(video, 'duration') else 'Unknown'}"
                    )
                    print(
                        f"     Language: {video.language.name if video.language else 'Unknown'}"
                    )
                    print()
        else:
            print("No video recommendations found for this user.")
    except Exception as e:
        print(f"Error getting video recommendations: {e}")

    print_separator()
    print("Test completed successfully!")


def main():
    """Main function to run the test."""
    parser = argparse.ArgumentParser(
        description="Test classroom recommendations for a Zeeguu user"
    )
    parser.add_argument("email", help="Email address of the user to test")
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="Number of recommendations to retrieve (default: 20)",
    )
    parser.add_argument(
        "--no-details",
        action="store_true",
        help="Show only basic information without details",
    )

    args = parser.parse_args()

    test_user_recommendations(
        args.email, show_details=not args.no_details, count=args.count
    )


if __name__ == "__main__":
    main()
