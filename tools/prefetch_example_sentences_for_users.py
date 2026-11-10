#!/usr/bin/env python3

"""
Nightly example prefetch: writes example sentences ahead of time, so that
exercises do not wait for an LLM.

Writes examples at the learner's level, for the words the exercises will
show next: scheduled words and the next new ones. A meaning is covered once
it has EXAMPLES_PER_LEVEL usable examples at or below the learner's level.
Learners who were active most recently come first, so a run capped with
--max-words serves those practicing now.

Usage:
    python -m tools.prefetch_example_sentences_for_users --all [--dry-run] [--max-words N]
    python -m tools.prefetch_example_sentences_for_users --user-id 123
"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional, Tuple

import zeeguu.core
from zeeguu.core.model import User, UserWord, ExampleSentence
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.exercises.example_contexts import (
    CEFR_LEVELS,
    anchorable_examples,
    learner_example_level,
    only_usable_examples,
    usable_examples_query,
)
from zeeguu.core.llm_services import get_llm_service
from zeeguu.core.llm_services.prompts import CURRENT_PROMPT_VERSION
from zeeguu.logging import log
from zeeguu.core.model.db import db
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer


EXAMPLES_PER_LEVEL = 3  # usable examples at or below the learner's level
NEW_WORDS_AHEAD = 10  # unscheduled words the exercises will introduce next


def words_the_exercises_will_show(user: User, all_words: bool = False) -> List[UserWord]:
    """
    The learner's scheduled words, and the next unscheduled ones the exercises
    will introduce (BasicSRSchedule.user_words_to_study takes them in the same
    order). Scheduled words alone are not enough: a word gets a schedule only
    at its first exercise, and that is when its context gets swapped for an
    example (zeeguu/core/exercises/example_contexts.py).
    """
    from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

    if all_words:
        return BasicSRSchedule.user_words_not_scheduled(user, None) + (
            BasicSRSchedule._scheduled_user_words_query(user).all()
        )
    return BasicSRSchedule._scheduled_user_words_query(user).all() + (
        BasicSRSchedule.user_words_not_scheduled(user, NEW_WORDS_AHEAD)
    )


def meanings_with_examples_up_to(meaning_ids, cefr_level: str, needed: int) -> set:
    """Of these meanings, those with `needed` usable examples at or below the
    level: usable_examples_query's rule, counted for many meanings at once."""
    from sqlalchemy import func

    if not meaning_ids:
        return set()
    query = db.session.query(ExampleSentence.meaning_id).filter(ExampleSentence.meaning_id.in_(meaning_ids))
    rows = (
        only_usable_examples(query, cefr_level)
        .group_by(ExampleSentence.meaning_id)
        .having(func.count(ExampleSentence.id) >= needed)
    )
    return {row.meaning_id for row in rows}


def get_user_words_needing_examples(
    user: Optional[User] = None,
    target_examples: int = EXAMPLES_PER_LEVEL,
    all_words: bool = False,
    days_active_threshold: int = 30,
) -> List[Tuple[UserWord, str]]:
    """
    (user word, learner's level) for each word the exercises will show that
    has fewer than `target_examples` usable examples at or below the learner's
    level. Examples belong to the meaning, so a meaning needed by several
    learners at one level comes once.

    Before 9 Nov 2026 examples were written at a level guessed from word rank,
    for scheduled words only, and an A2 learner's new words came with no
    examples or B1-C2 ones (user 6885).
    """
    from datetime import timedelta

    if user:
        users = [user]
    else:
        cutoff = datetime.now() - timedelta(days=days_active_threshold)
        # Most recently active first: --max-words cuts the end of this list
        users = User.query.filter(User.last_seen > cutoff).order_by(User.last_seen.desc()).all()
        log(f"{len(users)} learners active since {cutoff}")

    needing = []
    seen = set()
    for each in users:
        level = learner_example_level(each, each.learned_language)
        words = words_the_exercises_will_show(each, all_words)
        covered = meanings_with_examples_up_to(
            {w.meaning_id for w in words}, level, target_examples
        )
        for user_word in words:
            key = (user_word.meaning_id, level)
            if user_word.meaning_id in covered or key in seen:
                continue
            seen.add(key)
            needing.append((user_word, level))
    return needing


def generate_examples_for_user_word(
    user_word: UserWord, cefr_level: str, target_example_count: int = EXAMPLES_PER_LEVEL
) -> List[ExampleSentence]:
    """
    Write examples at `cefr_level` until the word's meaning has
    `target_example_count` usable ones at or below that level.
    """
    # Validate translation first (may fix it)
    from zeeguu.core.llm_services.validation_service import UserWordValidationService
    validated_user_word = UserWordValidationService.validate_and_fix(db.session, user_word)
    if validated_user_word is None:
        log(f"User word {user_word.id} failed validation, skipping example generation")
        return []

    # Use the validated (possibly fixed) user_word
    user_word = validated_user_word

    # Validation may have moved the word to another meaning
    if user_word.meaning_id in meanings_with_examples_up_to(
        {user_word.meaning_id}, cefr_level, target_example_count
    ):
        log(f"User word {user_word.id} already has {target_example_count} examples up to {cefr_level}")
        return []

    existing_count = usable_examples_query(user_word.meaning_id, cefr_level).count()
    examples_to_generate = target_example_count - existing_count

    origin_word = user_word.meaning.origin.content
    translation = user_word.meaning.translation.content
    origin_lang = user_word.meaning.origin.language.code
    translation_lang = user_word.meaning.translation.language.code

    try:
        log(f"Getting LLM service for word: {origin_word}")
        llm_service = get_llm_service()
        log(f"Using LLM service: {type(llm_service).__name__}")

        log(
            f"Generating {examples_to_generate} {cefr_level} examples for '{origin_word}' -> '{translation}'"
        )
        # Generate the needed number of examples
        examples = llm_service.generate_examples(
            word=origin_word,
            translation=translation,
            source_lang=origin_lang,
            target_lang=translation_lang,
            cefr_level=cefr_level,
            prompt_version=CURRENT_PROMPT_VERSION,
            count=examples_to_generate,
        )
        examples = anchorable_examples(examples, origin_word, user_word.meaning.origin.language)

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
        log(f"Generated {len(created_examples)} examples for user_word {user_word.id}")
        return created_examples

    except Exception:
        # The caller logs it and counts it as an error; a quiet [] would
        # count as "processed" and hide failures from the run summary.
        db.session.rollback()
        raise


def send_completion_notification(stats: dict, user: Optional[User] = None, send_email: bool = False):
    """
    Send email notification when batch generation completes.
    
    Args:
        stats: Dictionary with generation statistics
        user: Specific user if generation was for single user, None for all users
        send_email: If True, send the email notification
    """
    if not send_email:
        log("Email notification not requested, skipping")
        return
        
    try:
        duration_minutes = stats["duration_seconds"] / 60
        
        # Create subject
        if user:
            scope = f"user {user.name} ({user.id})"
        else:
            scope = "all active users"
            
        subject = f"📝 Example Prefetch Complete - {scope}"
        
        # Create detailed body
        body = f"""Batch Example Generation Completed

Scope: {scope}
Started: {stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
Completed: {stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}
Duration: {duration_minutes:.1f} minutes

Results:
- Words processed: {stats['processed']}/{stats['total_words']}
- Examples created: {stats['examples_created']}
- Errors encountered: {stats['errors']}
- Success rate: {(stats['processed'] - stats['errors']) / max(stats['processed'], 1) * 100:.1f}%
- First example ID: {stats['first_example_id'] or 'None'}
- Last example ID: {stats['last_example_id'] or 'None'}

Performance:
- Average time per word: {stats['duration_seconds'] / max(stats['processed'], 1):.2f} seconds
- Examples per minute: {stats['examples_created'] / max(duration_minutes, 0.1):.1f}

Status: {'✅ Success' if stats['errors'] == 0 else '⚠️ Completed with errors'}

---
Generated by Zeeguu Example Prefetch System
"""
        
        # Send to team email
        mailer = ZeeguuMailer(
            subject,
            body,
            "zeeguu.team@gmail.com"
        )
        mailer.send()
        log(f"Sent completion notification email for batch generation")
        
    except Exception as e:
        # Don't fail the whole process if email fails
        log(f"Failed to send completion notification: {e}")
        import traceback
        log(f"Email error traceback: {traceback.format_exc()}")


def batch_generate_examples(
    user: Optional[User] = None,
    target_examples: int = EXAMPLES_PER_LEVEL,
    max_words: Optional[int] = None,
    all_words: bool = False,
    days_active_threshold: int = 30,
    send_email: bool = False,
) -> dict:
    """
    Main function to batch generate examples.

    Args:
        user: Specific user to generate for, or None for all active learners
        target_examples: Usable examples each meaning should have at or below the learner's level
        max_words: Maximum number of words to process (spreads a backlog over several nights)
        all_words: All the learner's words, not only those the exercises will show next
        days_active_threshold: Number of days to consider for "active" users
        send_email: If True, send completion notification email

    Returns:
        Dictionary with generation statistics
    """
    start_time = datetime.now()

    user_words = get_user_words_needing_examples(
        user, target_examples, all_words, days_active_threshold
    )

    if max_words:
        user_words = user_words[:max_words]

    total_words = len(user_words)
    processed = 0
    examples_created = 0
    errors = 0
    first_example_id = None
    last_example_id = None

    log(f"Starting batch generation for {total_words} user words")

    # Test database connection
    current_count = ExampleSentence.query.count()
    log(f"Current ExampleSentence count in database: {current_count}")

    for i, (user_word, cefr_level) in enumerate(user_words):
        try:
            log(f"Processing {i+1}/{total_words}: {user_word.meaning.origin.content} ({cefr_level})")

            examples = generate_examples_for_user_word(user_word, cefr_level, target_examples)

            if examples:
                log(
                    f"Successfully generated {len(examples)} examples for '{user_word.meaning.origin.content}'"
                )
                examples_created += len(examples)
                
                # Track first and last example IDs
                for example in examples:
                    if first_example_id is None:
                        first_example_id = example.id
                    last_example_id = example.id
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
        "first_example_id": first_example_id,
        "last_example_id": last_example_id,
    }

    log(f"Batch generation completed: {stats}")

    # Check if examples were actually saved
    if examples_created > 0:
        total_in_db = ExampleSentence.query.count()
        log(f"Total ExampleSentence records in database: {total_in_db}")

    from zeeguu.operations.task_status import set_summary

    set_summary(
        f"{stats['processed']}/{stats['total_words']} words, "
        f"{stats['examples_created']} examples, {stats['errors']} errors"
    )

    # Send completion notification email
    send_completion_notification(stats, user, send_email)

    return stats


def main():
    from zeeguu.api.app import create_app_for_scripts

    app = create_app_for_scripts()
    app.app_context().push()

    parser = argparse.ArgumentParser(description="Batch generate example sentences")
    parser.add_argument("--all", action="store_true", help="Generate for all users")
    parser.add_argument("--user-id", type=int, help="Generate for specific user ID")
    parser.add_argument(
        "--target-examples",
        type=int,
        default=EXAMPLES_PER_LEVEL,
        help="Usable examples each meaning should have at or below the learner's level",
    )
    parser.add_argument(
        "--max-words", type=int, help="Maximum number of words to process (spreads a backlog over nights)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually generating",
    )
    parser.add_argument(
        "--all-words",
        action="store_true",
        help="All the learner's words, not only those the exercises will show next",
    )
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="Send completion notification email when finished",
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

    if args.dry_run:
        user_words = get_user_words_needing_examples(user, args.target_examples, args.all_words, 30)
        if args.max_words:
            user_words = user_words[: args.max_words]

        print(f"Would process {len(user_words)} user words")
        for level in CEFR_LEVELS:
            at_level = sum(1 for _, each in user_words if each == level)
            if at_level:
                print(f"  {level}: {at_level}")
        for uw, level in user_words[:10]:
            print(f"  - {uw.meaning.origin.content} ({level}, user {uw.user_id})")
        if len(user_words) > 10:
            print(f"  ... and {len(user_words) - 10} more")
        return

    stats = batch_generate_examples(
        user=user,
        target_examples=args.target_examples,
        max_words=args.max_words,
        all_words=args.all_words,
        days_active_threshold=30,
        send_email=args.send_email,
    )

    print(f"Generation completed:")
    print(f"  Words processed: {stats['processed']}/{stats['total_words']}")
    print(f"  Examples created: {stats['examples_created']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Duration: {stats['duration_seconds']:.1f} seconds")


if __name__ == "__main__":
    main()
