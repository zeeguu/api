#!/usr/bin/env python3
"""
Batch Validation Script for Existing Scheduled Meanings

Validates translations for user_words that are already scheduled but have
validated=0 (legacy data from before the validation feature).

Only processes words for users active in the last N days (default 30).
Inactive users' words are left unvalidated to save API calls.

This is a one-time migration script to bring existing data up to date.
New words are validated at scheduling time via FourLevelsPerWord.find_or_create().

Usage:
    python -m tools.validate_scheduled_meanings --dry-run --all
    python -m tools.validate_scheduled_meanings --max-words 100
    python -m tools.validate_scheduled_meanings --all
    python -m tools.validate_scheduled_meanings --all --days-active 60
"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional

import zeeguu.core
from zeeguu.core.model import UserWord, User, Meaning
from zeeguu.core.model.db import db
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.logging import log


def get_scheduled_words_needing_validation(
    max_words: Optional[int] = None,
    user_id: Optional[int] = None,
    days_active: int = 30,
) -> List[UserWord]:
    """
    Get user_words that are scheduled but not yet validated.

    Only includes words for users active in the last N days.
    These are legacy words from before the validation feature was deployed.
    """
    from datetime import timedelta

    query = (
        UserWord.query
        .join(BasicSRSchedule, BasicSRSchedule.user_word_id == UserWord.id)
        .join(Meaning, UserWord.meaning_id == Meaning.id)
        .filter(Meaning.validated == 0)
        .filter(UserWord.fit_for_study == True)
    )

    if user_id:
        query = query.filter(UserWord.user_id == user_id)
    else:
        # Only validate for active users (saves API calls on abandoned accounts)
        cutoff_date = datetime.now() - timedelta(days=days_active)
        query = query.filter(UserWord.user.has(User.last_seen > cutoff_date))
        log(f"Filtering to users active since {cutoff_date}")

    # Order by user to batch context switches
    query = query.order_by(UserWord.user_id)

    if max_words:
        query = query.limit(max_words)

    return query.all()


def validate_user_word(user_word: UserWord) -> dict:
    """
    Validate a single user_word and return result info.

    Returns dict with: success, action (valid/fixed/invalid/skipped), details
    """
    from zeeguu.core.llm_services.validation_service import UserWordValidationService

    meaning = user_word.meaning
    original_word = meaning.origin.content
    original_translation = meaning.translation.content

    try:
        result_user_word = UserWordValidationService.validate_and_fix(db.session, user_word)

        if result_user_word is None:
            return {
                "success": True,
                "action": "invalid",
                "details": f"'{original_word}' -> '{original_translation}' marked invalid (no correction available)"
            }
        elif result_user_word.id != user_word.id:
            new_meaning = result_user_word.meaning
            return {
                "success": True,
                "action": "fixed",
                "details": f"'{original_word}' -> '{original_translation}' fixed to '{new_meaning.origin.content}' -> '{new_meaning.translation.content}'"
            }
        elif meaning.validated == 1:
            return {
                "success": True,
                "action": "valid",
                "details": f"'{original_word}' -> '{original_translation}' validated as correct"
            }
        else:
            return {
                "success": True,
                "action": "skipped",
                "details": f"'{original_word}' -> '{original_translation}' skipped (no context)"
            }

    except Exception as e:
        return {
            "success": False,
            "action": "error",
            "details": f"'{original_word}' -> '{original_translation}' error: {str(e)}"
        }


def batch_validate(
    max_words: Optional[int] = None,
    user_id: Optional[int] = None,
    days_active: int = 30,
    dry_run: bool = False,
) -> dict:
    """
    Validate all scheduled words that haven't been validated yet.

    Only processes words for users active in the last days_active days.
    Returns statistics dict.
    """
    start_time = datetime.now()

    user_words = get_scheduled_words_needing_validation(max_words, user_id, days_active)
    total = len(user_words)

    log(f"Found {total} scheduled user_words needing validation")

    if dry_run:
        print(f"\n[DRY RUN] Would validate {total} user_words:")
        for uw in user_words[:20]:
            print(f"  - {uw.meaning.origin.content} -> {uw.meaning.translation.content} (user {uw.user_id})")
        if total > 20:
            print(f"  ... and {total - 20} more")
        return {"total": total, "dry_run": True}

    stats = {
        "total": total,
        "valid": 0,
        "fixed": 0,
        "invalid": 0,
        "skipped": 0,
        "errors": 0,
    }

    for i, user_word in enumerate(user_words):
        log(f"[{i+1}/{total}] Validating user_word {user_word.id}")

        result = validate_user_word(user_word)
        action = result["action"]

        if action in stats:
            stats[action] += 1

        log(f"  {result['action'].upper()}: {result['details']}")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    stats["duration_seconds"] = duration
    stats["start_time"] = start_time
    stats["end_time"] = end_time

    return stats


def main():
    from zeeguu.api.app import create_app

    app = create_app()
    app.app_context().push()

    parser = argparse.ArgumentParser(
        description="Validate scheduled meanings that haven't been validated yet"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Validate all scheduled words needing validation"
    )
    parser.add_argument(
        "--max-words", type=int,
        help="Maximum number of words to validate"
    )
    parser.add_argument(
        "--user-id", type=int,
        help="Only validate words for a specific user"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be validated without making changes"
    )
    parser.add_argument(
        "--days-active", type=int, default=30,
        help="Only validate for users active in the last N days (default: 30)"
    )

    args = parser.parse_args()

    if not args.all and not args.max_words and not args.user_id:
        print("Error: Must specify --all, --max-words, or --user-id")
        print("Use --dry-run to preview changes")
        sys.exit(1)

    stats = batch_validate(
        max_words=args.max_words,
        user_id=args.user_id,
        days_active=args.days_active,
        dry_run=args.dry_run,
    )

    if not args.dry_run:
        print(f"\nValidation completed:")
        print(f"  Total processed: {stats['total']}")
        print(f"  Valid: {stats['valid']}")
        print(f"  Fixed: {stats['fixed']}")
        print(f"  Invalid: {stats['invalid']}")
        print(f"  Skipped: {stats['skipped']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Duration: {stats['duration_seconds']:.1f} seconds")


if __name__ == "__main__":
    main()
