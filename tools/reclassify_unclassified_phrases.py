#!/usr/bin/env python
"""
Reclassify unclassified multi-word phrases for recently active users.

This script:
1. Finds users active in the last N days
2. Gets their unclassified multi-word user_words (phrase_type = NULL)
3. Classifies them using the LLM
4. Updates meanings and automatically unschedules words marked as arbitrary_multi_word

Usage:
    python tools/reclassify_unclassified_phrases.py [--days 30] [--limit 100] [--dry-run]
"""

import sys
import os
from datetime import datetime, timedelta
import argparse
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# REQUIRED: Initialize Flask app context for database access
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

# Now safe to import and use models
from zeeguu.core.model import User, UserWord, Meaning, Phrase
from zeeguu.core.model.meaning_frequency_classifier import MeaningFrequencyClassifier
from zeeguu.logging import logp


def get_recently_active_users(days=30):
    """
    Get users who have been active in the last N days.
    Active = created user_words or exercise activity.

    Args:
        days: Number of days to look back

    Returns:
        List of User objects
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    # Find users with recent user_words
    users = (
        db.session.query(User)
        .join(UserWord, UserWord.user_id == User.id)
        .filter(UserWord.time >= cutoff_date)
        .distinct()
        .all()
    )

    return users


def get_unclassified_multi_word_meanings(user):
    """
    Get unclassified multi-word meanings for a user.

    Args:
        user: User object

    Returns:
        List of (UserWord, Meaning) tuples
    """
    results = (
        db.session.query(UserWord, Meaning)
        .join(Meaning, UserWord.meaning_id == Meaning.id)
        .join(Phrase, Meaning.origin_id == Phrase.id)
        .filter(UserWord.user_id == user.id)
        .filter(Meaning.phrase_type.is_(None))  # Unclassified
        .filter(Phrase.content.like('% %'))  # Has spaces (multi-word)
        .all()
    )

    return results


def reclassify_for_users(users, limit=None, dry_run=False, batch_size=15, interactive=False):
    """
    Reclassify unclassified phrases for given users using batch classification.

    Args:
        users: List of User objects
        limit: Maximum number of meanings to classify (None = no limit)
        dry_run: If True, don't actually update the database
        batch_size: Number of meanings to classify per API call (default 15)
        interactive: If True, ask for confirmation before unscheduling arbitrary_multi_word phrases

    Returns:
        Dict with statistics
    """
    classifier = MeaningFrequencyClassifier()

    stats = {
        'users_processed': 0,
        'meanings_found': 0,
        'meanings_classified': 0,
        'meanings_failed': 0,
        'arbitrary_multi_word': 0,
        'collocations': 0,
        'idioms': 0,
        'expressions': 0,
        'single_word': 0,
    }

    total_classified = 0

    for user in users:
        stats['users_processed'] += 1
        logp(f"\n{'='*80}")
        logp(f"Processing user {user.id} ({user.name})")

        # Get unclassified multi-word meanings for this user
        user_word_meanings = get_unclassified_multi_word_meanings(user)
        stats['meanings_found'] += len(user_word_meanings)

        if not user_word_meanings:
            logp(f"  No unclassified multi-word phrases found")
            continue

        logp(f"  Found {len(user_word_meanings)} unclassified multi-word phrases")

        # Extract unique meanings (avoid duplicates)
        seen_meaning_ids = set()
        meanings_to_classify = []
        for user_word, meaning in user_word_meanings:
            if meaning.id not in seen_meaning_ids:
                seen_meaning_ids.add(meaning.id)
                meanings_to_classify.append(meaning)

        logp(f"  Unique meanings to classify: {len(meanings_to_classify)}")

        # Process in batches
        for batch_start in range(0, len(meanings_to_classify), batch_size):
            # Check limit
            if limit and total_classified >= limit:
                logp(f"\nReached limit of {limit} classifications. Stopping.")
                return stats

            # Get current batch
            batch_end = min(batch_start + batch_size, len(meanings_to_classify))
            if limit:
                batch_end = min(batch_end, batch_start + (limit - total_classified))

            batch = meanings_to_classify[batch_start:batch_end]

            logp(f"\n  Batch {batch_start//batch_size + 1}: Classifying {len(batch)} meanings...")

            if dry_run:
                for meaning in batch:
                    logp(f"    [DRY RUN] Would classify: '{meaning.origin.content}' → '{meaning.translation.content}'")
                    stats['meanings_classified'] += 1
                    total_classified += 1
                continue

            # Classify batch
            batch_stats = classifier.classify_and_update_meanings_batch(batch, db.session)

            # Update stats
            stats['meanings_classified'] += batch_stats['classified']
            stats['meanings_failed'] += batch_stats['failed']
            total_classified += batch_stats['classified']

            # Log results and handle interactive confirmation for arbitrary_multi_word
            from zeeguu.core.model.meaning import PhraseType

            for meaning in batch:
                if meaning.phrase_type:
                    phrase_type_str = meaning.phrase_type.value
                    stats[phrase_type_str] = stats.get(phrase_type_str, 0) + 1

                    logp(f"    ✓ '{meaning.origin.content}': {meaning.frequency.value if meaning.frequency else 'unknown'}, {phrase_type_str}")

                    # Handle arbitrary_multi_word interactively
                    if meaning.phrase_type == PhraseType.ARBITRARY_MULTI_WORD:
                        if interactive:
                            logp(f"      ⚠️  Classified as arbitrary_multi_word (not a good unit of study)")
                            logp(f"         Translation: '{meaning.translation.content}'")
                            response = input(f"         Unschedule this word? [Y/n/q(uit)]: ").strip().lower()

                            if response == 'q' or response == 'quit':
                                logp("\n[Interactive mode] User quit. Stopping.")
                                return stats
                            elif response == 'n' or response == 'no':
                                logp(f"         Skipped - keeping as fit for study")
                                # Revert the classification for this meaning
                                meaning.phrase_type = None
                                meaning.frequency = None
                                db.session.add(meaning)
                                db.session.commit()
                                # Update fit_for_study back
                                classifier._update_user_words_fit_for_study(meaning, db.session)
                                stats['arbitrary_multi_word'] -= 1
                                continue
                            else:
                                logp(f"         ✓ Unscheduling (marked as NOT fit for study)")
                        else:
                            logp(f"      ⚠️  Marked as NOT fit for study")
                elif meaning.frequency:
                    logp(f"    ✓ '{meaning.origin.content}': {meaning.frequency.value} (phrase_type classification failed)")
                else:
                    logp(f"    ✗ '{meaning.origin.content}': Classification failed")

            # Small delay between batches
            if batch_end < len(meanings_to_classify):
                time.sleep(0.5)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Reclassify unclassified multi-word phrases for recently active users'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to look back for active users (default: 30)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of meanings to classify (default: no limit)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually doing it'
    )
    parser.add_argument(
        '--user-id',
        type=int,
        default=None,
        help='Process only a specific user ID'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=15,
        help='Number of meanings to classify per API call (default: 15)'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Ask for confirmation before unscheduling arbitrary_multi_word phrases'
    )

    args = parser.parse_args()

    logp("="*80)
    logp("Reclassifying Unclassified Multi-Word Phrases")
    logp("="*80)
    logp(f"Configuration:")
    logp(f"  Days lookback: {args.days}")
    logp(f"  Limit: {args.limit if args.limit else 'No limit'}")
    logp(f"  Batch size: {args.batch_size}")
    logp(f"  Interactive: {args.interactive}")
    logp(f"  Dry run: {args.dry_run}")
    logp(f"  Specific user: {args.user_id if args.user_id else 'All recently active'}")
    logp("")

    # Get users to process
    if args.user_id:
        users = [User.query.get(args.user_id)]
        if not users[0]:
            logp(f"Error: User {args.user_id} not found")
            return
        logp(f"Processing single user: {users[0].name}")
    else:
        logp(f"Finding users active in last {args.days} days...")
        users = get_recently_active_users(args.days)
        logp(f"Found {len(users)} recently active users")

    if not users:
        logp("No users to process")
        return

    # Process users
    stats = reclassify_for_users(
        users,
        limit=args.limit,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        interactive=args.interactive
    )

    # Print summary
    logp("\n" + "="*80)
    logp("SUMMARY")
    logp("="*80)
    logp(f"Users processed: {stats['users_processed']}")
    logp(f"Unclassified meanings found: {stats['meanings_found']}")
    logp(f"Meanings classified: {stats['meanings_classified']}")
    logp(f"Meanings failed: {stats['meanings_failed']}")
    logp("")
    logp("Classification breakdown:")
    logp(f"  - Arbitrary multi-word (unscheduled): {stats['arbitrary_multi_word']}")
    logp(f"  - Collocations: {stats.get('collocation', 0)}")
    logp(f"  - Idioms: {stats.get('idiom', 0)}")
    logp(f"  - Expressions: {stats.get('expression', 0)}")
    logp(f"  - Single word: {stats.get('single_word', 0)}")

    if args.dry_run:
        logp("\n[DRY RUN] No changes were made to the database")


if __name__ == '__main__':
    main()
