#!/usr/bin/env python3

"""
Batch Example Generator Tool

Pre-generates example sentences for all user words to avoid real-time LLM calls.
This tool can be run periodically (e.g., nightly) to ensure users have
instant access to example sentences.

Usage:
    python -m tools.example_batch_generator --all
    python -m tools.example_batch_generator --user-id 123
    python -m tools.example_batch_generator --missing-only
"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional

import zeeguu.core
from zeeguu.core.model import User, UserWord, ExampleSentence
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.example_generation.llm_service import get_llm_service
from zeeguu.logging import log
from zeeguu.core.model.db import db


def get_user_words_needing_examples(
    user: Optional[User] = None,
    missing_only: bool = False,
    min_examples_threshold: int = 5,
    scheduled_only: bool = True,
    active_users_only: bool = True,
    days_active_threshold: int = 30,
) -> List[UserWord]:
    """
    Get user words that need example sentences generated.

    Args:
        user: Specific user to generate for, or None for all users
        missing_only: Only return user words with fewer than min_examples_threshold examples
        min_examples_threshold: Minimum number of examples each word should have
        scheduled_only: Only include words that are currently scheduled for study
        active_users_only: Only include words for users active in the last N days
        days_active_threshold: Number of days to consider for "active" users

    Returns:
        List of UserWord objects needing examples
    """
    from sqlalchemy import func
    from zeeguu.core.model import Meaning, Phrase
    from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

    query = UserWord.query.filter(UserWord.fit_for_study == True)

    if user:
        query = query.filter(UserWord.user_id == user.id)

    if scheduled_only:
        # Only include words that have a schedule (are actively being studied)
        query = query.join(BasicSRSchedule, BasicSRSchedule.user_word_id == UserWord.id)

    if missing_only:
        # Only get user words that have fewer than N example sentences
        # Using a subquery to count existing examples per meaning
        example_count_subquery = (
            db.session.query(
                ExampleSentence.meaning_id,
                func.count(ExampleSentence.id).label("example_count"),
            )
            .group_by(ExampleSentence.meaning_id)
            .subquery()
        )

        # Left join to include meanings with zero examples
        query = query.outerjoin(
            example_count_subquery,
            UserWord.meaning_id == example_count_subquery.c.meaning_id,
        ).filter(
            (example_count_subquery.c.example_count == None)
            | (example_count_subquery.c.example_count < min_examples_threshold)
        )

    # Prioritize by word frequency (most common words first)
    query = (
        query.join(Meaning, UserWord.meaning_id == Meaning.id)
        .join(Phrase, Meaning.origin_id == Phrase.id)
        .order_by(Phrase.rank)
    )

    # Apply active users filter if needed - much more efficient with last_seen
    if active_users_only and not user:  # Only filter by activity if processing all users
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days_active_threshold)
        
        # Use the user relationship instead of explicit join to avoid cartesian product
        query = query.filter(
            UserWord.user.has(User.last_seen > cutoff_date)
        )
        log(f"Filtering to users active since {cutoff_date}")

    return query.all()


def generate_examples_for_user_word(
    user_word: UserWord, target_example_count: int = 5
) -> List[ExampleSentence]:
    """
    Generate multiple example sentences for a single user word.

    Args:
        user_word: The UserWord to generate examples for
        target_example_count: Target total number of examples (will generate enough to reach this count)

    Returns:
        List of created ExampleSentence objects
    """
    # Check how many examples already exist
    existing_count = ExampleSentence.query.filter(
        ExampleSentence.meaning_id == user_word.meaning_id
    ).count()

    # Calculate how many more we need
    examples_to_generate = max(0, target_example_count - existing_count)

    if examples_to_generate == 0:
        log(f"User word {user_word.id} already has {existing_count} examples, skipping")
        return []
    origin_word = user_word.meaning.origin.content
    translation = user_word.meaning.translation.content
    origin_lang = user_word.meaning.origin.language.code
    translation_lang = user_word.meaning.translation.language.code

    # Determine CEFR level based on user's level or word frequency
    cefr_level = determine_cefr_level(user_word)

    try:
        log(f"Getting LLM service for word: {origin_word}")
        llm_service = get_llm_service()
        log(f"Using LLM service: {type(llm_service).__name__}")

        log(
            f"Generating {examples_to_generate} examples for '{origin_word}' -> '{translation}'"
        )
        # Generate the needed number of examples
        examples = llm_service.generate_examples(
            word=origin_word,
            translation=translation,
            source_lang=origin_lang,
            target_lang=translation_lang,
            cefr_level=cefr_level,
            count=examples_to_generate,
        )

        # Get or create AIGenerator record
        llm_model = examples[0]["llm_model"] if examples else "unknown"
        prompt_version = examples[0]["prompt_version"] if examples else "v1"

        ai_generator = AIGenerator.find_or_create(
            db.session,
            llm_model,
            prompt_version,
            description="Batch example generation for language learning",
        )

        created_examples = []
        for example in examples:
            log(f"Creating ExampleSentence: '{example['sentence'][:50]}...'")
            example_sentence = ExampleSentence.create_ai_generated(
                db.session,
                sentence=example["sentence"],
                language=user_word.meaning.origin.language,
                meaning=user_word.meaning,
                ai_generator=ai_generator,
                translation=example.get("translation"),
                cefr_level=example.get("cefr_level", cefr_level),
                commit=False,
            )
            created_examples.append(example_sentence)

        # Commit immediately after creating each set of examples
        db.session.commit()
        log(f"Committed {len(created_examples)} examples for user_word {user_word.id}")

        for i, example_sentence in enumerate(created_examples):
            log(f"Created and committed ExampleSentence with ID: {example_sentence.id}")

        log(f"Generated {len(created_examples)} examples for user_word {user_word.id}")
        return created_examples

    except Exception as e:
        import traceback

        log(f"Error generating examples for user_word {user_word.id}: {e}")
        log(f"Full traceback: {traceback.format_exc()}")
        return []


def determine_cefr_level(user_word: UserWord) -> str:
    """
    Determine appropriate CEFR level for a user word based on:
    - User's overall level
    - Word frequency/rank
    - User's learning progress
    """
    # For now, use a simple heuristic based on word rank
    word_rank = user_word.meaning.origin.rank or 100000

    if word_rank <= 1000:
        return "A1"
    elif word_rank <= 3000:
        return "A2"
    elif word_rank <= 5000:
        return "B1"
    elif word_rank <= 10000:
        return "B2"
    elif word_rank <= 20000:
        return "C1"
    else:
        return "C2"


def batch_generate_examples(
    user: Optional[User] = None,
    missing_only: bool = False,
    target_examples_per_word: int = 5,
    batch_size: int = 1,
    max_words: Optional[int] = None,
    scheduled_only: bool = True,
    active_users_only: bool = True,
    days_active_threshold: int = 30,
) -> dict:
    """
    Main function to batch generate examples.

    Args:
        user: Specific user to generate for
        missing_only: Only generate for words with fewer than target_examples_per_word examples
        target_examples_per_word: Target total number of examples per word (will generate enough to reach this)
        batch_size: Number of words to process before committing
        max_words: Maximum number of words to process (for testing)
        scheduled_only: Only include words that are currently scheduled for study

    Returns:
        Dictionary with generation statistics
    """
    start_time = datetime.now()

    user_words = get_user_words_needing_examples(
        user, missing_only, target_examples_per_word, scheduled_only, active_users_only, days_active_threshold
    )

    if max_words:
        user_words = user_words[:max_words]

    total_words = len(user_words)
    processed = 0
    examples_created = 0
    errors = 0

    log(f"Starting batch generation for {total_words} user words")

    # Test database connection
    current_count = ExampleSentence.query.count()
    log(f"Current ExampleSentence count in database: {current_count}")

    for i, user_word in enumerate(user_words):
        try:
            log(f"Processing {i+1}/{total_words}: {user_word.meaning.origin.content}")

            examples = generate_examples_for_user_word(
                user_word, target_examples_per_word
            )

            if examples:
                log(
                    f"Successfully generated {len(examples)} examples for '{user_word.meaning.origin.content}'"
                )
                examples_created += len(examples)
            else:
                log(
                    f"No examples generated for '{user_word.meaning.origin.content}' (might already have enough)"
                )

            processed += 1
            
            # Examples are now committed immediately in generate_examples_for_user_word()
            # No need for batch commits

        except Exception as e:
            import traceback

            log(f"Error processing user_word {user_word.id}: {e}")
            log(f"Full traceback: {traceback.format_exc()}")
            errors += 1
            continue

    # Final commit
    log(f"Final commit - {examples_created} total examples created")
    try:
        db.session.commit()
        log("Final commit completed successfully")
        final_count = ExampleSentence.query.count()
        log(f"Final ExampleSentence count: {final_count}")
    except Exception as final_commit_error:
        log(f"FINAL COMMIT FAILED: {final_commit_error}")
        import traceback
        log(f"Final commit error traceback: {traceback.format_exc()}")
        db.session.rollback()
        log("Final session rolled back")

    end_time = datetime.now()
    duration = end_time - start_time

    stats = {
        "total_words": total_words,
        "processed": processed,
        "examples_created": examples_created,
        "errors": errors,
        "duration_seconds": duration.total_seconds(),
        "start_time": start_time,
        "end_time": end_time,
    }

    log(f"Batch generation completed: {stats}")

    # Check if examples were actually saved
    if examples_created > 0:
        total_in_db = ExampleSentence.query.count()
        log(f"Total ExampleSentence records in database: {total_in_db}")

    return stats


def main():
    from zeeguu.api.app import create_app

    app = create_app()
    app.app_context().push()

    parser = argparse.ArgumentParser(description="Batch generate example sentences")
    parser.add_argument("--all", action="store_true", help="Generate for all users")
    parser.add_argument("--user-id", type=int, help="Generate for specific user ID")
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Only generate for words with no existing examples",
    )
    parser.add_argument(
        "--target-examples",
        type=int,
        default=5,
        help="Target total number of examples per word (will generate enough to reach this)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of words to process before committing",
    )
    parser.add_argument(
        "--max-words", type=int, help="Maximum number of words to process (for testing)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually generating",
    )
    parser.add_argument(
        "--all-words",
        action="store_true",
        help="Include all user words, not just scheduled ones",
    )

    args = parser.parse_args()

    if not args.all and not args.user_id:
        print("Error: Must specify either --all or --user-id")
        sys.exit(1)

    user = None
    if args.user_id:
        user = User.find_by_id(args.user_id)
        if not user:
            print(f"Error: User with ID {args.user_id} not found")
            sys.exit(1)

    # By default, only process scheduled words unless --all-words is specified
    scheduled_only = not args.all_words

    if args.dry_run:
        user_words = get_user_words_needing_examples(
            user, args.missing_only, args.target_examples, scheduled_only, True, 30
        )
        if args.max_words:
            user_words = user_words[: args.max_words]

        scope = "scheduled" if scheduled_only else "all"
        print(f"Would process {len(user_words)} {scope} user words")
        for uw in user_words[:10]:  # Show first 10
            print(f"  - {uw.meaning.origin.content} ({uw.user.name})")
        if len(user_words) > 10:
            print(f"  ... and {len(user_words) - 10} more")
        return

    stats = batch_generate_examples(
        user=user,
        missing_only=args.missing_only,
        target_examples_per_word=args.target_examples,
        batch_size=args.batch_size,
        max_words=args.max_words,
        scheduled_only=scheduled_only,
        active_users_only=True,
        days_active_threshold=30,
    )

    print(f"Generation completed:")
    print(f"  Words processed: {stats['processed']}/{stats['total_words']}")
    print(f"  Examples created: {stats['examples_created']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Duration: {stats['duration_seconds']:.1f} seconds")


if __name__ == "__main__":
    main()
