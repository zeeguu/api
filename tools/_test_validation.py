#!/usr/bin/env python3
"""
Quick test script for the validation service.

Usage:
    # Test a specific user_word by ID
    python -m tools._test_validation --user-word-id 123

    # Test a specific user's first unvalidated word
    python -m tools._test_validation --user-id 534

    # Dry run (show what would be validated without calling LLM)
    python -m tools._test_validation --user-word-id 123 --dry-run
"""

import argparse
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import UserWord, Meaning
from zeeguu.core.llm_services.validation_service import UserWordValidationService


def find_unvalidated_user_word(user_id=None, user_word_id=None):
    """Find a user_word to test."""
    if user_word_id:
        return UserWord.query.get(user_word_id)

    query = UserWord.query.join(Meaning).filter(
        Meaning.validated != Meaning.VALID,
        UserWord.fit_for_study == True
    )

    if user_id:
        query = query.filter(UserWord.user_id == user_id)

    return query.first()


def main():
    parser = argparse.ArgumentParser(description="Test validation service")
    parser.add_argument("--user-word-id", type=int, help="Specific user_word ID to test")
    parser.add_argument("--user-id", type=int, help="Find first unvalidated word for this user")
    parser.add_argument("--dry-run", action="store_true", help="Show info without calling LLM")
    args = parser.parse_args()

    user_word = find_unvalidated_user_word(args.user_id, args.user_word_id)

    if not user_word:
        print("No unvalidated user_word found")
        return

    meaning = user_word.meaning
    bookmark = user_word.preferred_bookmark
    context = bookmark.get_context() if bookmark else None

    print(f"\n{'='*60}")
    print(f"UserWord ID: {user_word.id}")
    print(f"User: {user_word.user.name} (ID: {user_word.user_id})")
    print(f"Meaning ID: {meaning.id}")
    print(f"Word: '{meaning.origin.content}' ({meaning.origin.language.code})")
    print(f"Translation: '{meaning.translation.content}' ({meaning.translation.language.code})")
    print(f"Validated: {meaning.validated}")
    print(f"Fit for study: {user_word.fit_for_study}")
    print(f"Context: {context[:100] if context else 'None'}...")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("[DRY RUN] Would call validation service here")
        return

    print("Calling validation service...")
    result = UserWordValidationService.validate_and_fix(db.session, user_word)

    print(f"\n{'='*60}")
    if result is None:
        print("Result: None (unfixable, marked as invalid)")
    elif result.id != user_word.id:
        print(f"Result: Moved to new UserWord {result.id}")
        print(f"New word: '{result.meaning.origin.content}'")
        print(f"New translation: '{result.meaning.translation.content}'")
    else:
        print(f"Result: Same UserWord (validated={result.meaning.validated})")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
