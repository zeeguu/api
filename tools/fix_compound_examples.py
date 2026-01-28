#!/usr/bin/env python3
"""
Script to find and fix example sentences where the target word only appears
inside compound words (e.g., "forhold" in "Boligforhold" instead of standalone).

These examples are problematic for language learning because:
1. The word is hard to recognize inside a compound
2. Fill-in-the-blank exercises don't work well with compound words
3. Learners can't easily practice the word in isolation

Usage:
    # Dry run - just report bad examples
    python -m tools.fix_compound_examples --dry-run

    # Delete bad examples without regenerating
    python -m tools.fix_compound_examples --delete

    # Delete and regenerate new examples
    python -m tools.fix_compound_examples --delete --regenerate

    # Process specific meaning IDs
    python -m tools.fix_compound_examples --meaning-ids 123,456,789

    # Limit processing (for testing)
    python -m tools.fix_compound_examples --max-examples 100
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import ExampleSentence, Meaning, Phrase, Language
from zeeguu.core.model.example_sentence_context import ExampleSentenceContext
from zeeguu.core.tokenization.word_position_finder import word_appears_standalone
from zeeguu.logging import log


def has_underscore_formatting(word, sentence):
    """
    Check if a sentence has underscore formatting around a word.
    This catches LLM-generated examples like "Bolig_forhold_" instead of "Boligforhold".
    """
    import re
    # Look for patterns like: Word_word_, _word_, word_Word_
    # The word should be surrounded by or adjacent to underscores
    patterns = [
        rf'\w+_{re.escape(word)}_',  # Prefix_word_
        rf'_{re.escape(word)}_\w*',  # _word_ or _word_suffix
        rf'{re.escape(word)}_',      # word_ at end
        rf'_{re.escape(word)}',      # _word at end
    ]

    for pattern in patterns:
        if re.search(pattern, sentence, re.IGNORECASE):
            return True
    return False


def is_valid_contraction(word, compound):
    """
    Check if a "compound" is actually a valid contraction (like French l'été).
    Valid contractions have the target word at a clear boundary.
    """
    word_lower = word.lower()
    compound_lower = compound.lower()

    # Check if word is at the end after an apostrophe (e.g., l'été)
    if compound_lower.endswith(word_lower):
        prefix = compound_lower[:-len(word_lower)]
        if prefix.endswith("'") or prefix.endswith("'"):
            return True

    # Check if word is at the start before an apostrophe (e.g., c'est)
    if compound_lower.startswith(word_lower):
        suffix = compound_lower[len(word_lower):]
        if suffix.startswith("'") or suffix.startswith("'"):
            return True

    return False


def find_compound_only_examples(max_examples=None, meaning_ids=None):
    """
    Find examples where the target word only appears inside compound words
    or has underscore formatting issues.

    Returns:
        List of dicts with example info and issue type
    """
    query = (
        db.session.query(
            ExampleSentence.id,
            ExampleSentence.sentence,
            ExampleSentence.meaning_id,
            Phrase.content.label("word"),
            Language.code.label("lang_code"),
            Language.id.label("lang_id"),
        )
        .join(Meaning, ExampleSentence.meaning_id == Meaning.id)
        .join(Phrase, Meaning.origin_id == Phrase.id)
        .join(Language, Phrase.language_id == Language.id)
    )

    if meaning_ids:
        query = query.filter(ExampleSentence.meaning_id.in_(meaning_ids))

    if max_examples:
        query = query.limit(max_examples)

    examples = query.all()
    print(f"Checking {len(examples)} examples for compound-only words...")

    bad_examples = []

    for i, ex in enumerate(examples):
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(examples)} examples...")

        # First check for underscore formatting (the main bug)
        if has_underscore_formatting(ex.word, ex.sentence):
            bad_examples.append({
                'id': ex.id,
                'sentence': ex.sentence,
                'word': ex.word,
                'meaning_id': ex.meaning_id,
                'lang_code': ex.lang_code,
                'issue_type': 'underscore_formatting',
                'compounds': []
            })
            continue

        # Get language object for tokenization
        language = Language.find_by_id(ex.lang_id)

        # Check if word appears standalone
        result = word_appears_standalone(ex.word, ex.sentence, language)

        if result['only_in_compounds']:
            # Filter out valid contractions
            real_compounds = [
                c for c in result['compound_examples']
                if c and len(c) > 1 and not is_valid_contraction(ex.word, c)
            ]

            if real_compounds:
                bad_examples.append({
                    'id': ex.id,
                    'sentence': ex.sentence,
                    'word': ex.word,
                    'meaning_id': ex.meaning_id,
                    'lang_code': ex.lang_code,
                    'issue_type': 'compound_only',
                    'compounds': real_compounds
                })

    return bad_examples


def delete_examples(example_ids):
    """Delete examples by ID, skipping those linked to bookmarks."""
    if not example_ids:
        return 0, 0

    # Check which ones are linked to bookmarks
    linked_ids = set(
        row[0]
        for row in db.session.query(ExampleSentenceContext.example_sentence_id)
        .filter(ExampleSentenceContext.example_sentence_id.in_(example_ids))
        .all()
    )

    deletable_ids = set(example_ids) - linked_ids

    if deletable_ids:
        deleted_count = (
            db.session.query(ExampleSentence)
            .filter(ExampleSentence.id.in_(deletable_ids))
            .delete(synchronize_session=False)
        )
        db.session.commit()
    else:
        deleted_count = 0

    return deleted_count, len(linked_ids)


def regenerate_examples_for_meanings(meaning_ids, target_count=5):
    """Regenerate examples for specific meanings."""
    from zeeguu.core.llm_services import get_llm_service
    from zeeguu.core.model.ai_generator import AIGenerator

    llm_service = get_llm_service()
    regenerated_count = 0

    for meaning_id in meaning_ids:
        meaning = Meaning.query.get(meaning_id)
        if not meaning:
            print(f"  Warning: Meaning {meaning_id} not found, skipping")
            continue

        # Check how many examples already exist
        existing_count = ExampleSentence.query.filter(
            ExampleSentence.meaning_id == meaning_id
        ).count()

        examples_to_generate = max(0, target_count - existing_count)
        if examples_to_generate == 0:
            print(f"  Meaning {meaning_id} already has {existing_count} examples, skipping")
            continue

        origin_word = meaning.origin.content
        translation = meaning.translation.content
        origin_lang = meaning.origin.language.code
        translation_lang = meaning.translation.language.code

        print(f"  Generating {examples_to_generate} examples for '{origin_word}' -> '{translation}'...")

        try:
            examples = llm_service.generate_examples(
                word=origin_word,
                translation=translation,
                source_lang=origin_lang,
                target_lang=translation_lang,
                cefr_level="B1",  # Default level
                prompt_version="v3",
                count=examples_to_generate,
            )

            # Get or create AIGenerator record
            llm_model = examples[0]["llm_model"] if examples else "unknown"
            prompt_version = examples[0]["prompt_version"] if examples else "v3"

            ai_generator = AIGenerator.find_or_create(
                db.session,
                llm_model,
                prompt_version,
                description="Regenerated after compound word fix",
            )

            for example in examples:
                ExampleSentence.create_ai_generated(
                    db.session,
                    sentence=example["sentence"],
                    language=meaning.origin.language,
                    meaning=meaning,
                    ai_generator=ai_generator,
                    translation=example.get("translation"),
                    cefr_level=example.get("cefr_level", "B1"),
                    commit=False,
                )

            db.session.commit()
            regenerated_count += len(examples)
            print(f"    Created {len(examples)} new examples")

        except Exception as e:
            print(f"    Error generating examples: {e}")
            db.session.rollback()

    return regenerated_count


def main():
    parser = argparse.ArgumentParser(
        description="Find and fix examples where words only appear in compounds"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report bad examples, don't delete or regenerate",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete bad examples",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate examples for affected meanings (requires --delete)",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        help="Maximum number of examples to check (for testing)",
    )
    parser.add_argument(
        "--meaning-ids",
        type=str,
        help="Comma-separated list of meaning IDs to process",
    )

    args = parser.parse_args()

    if args.regenerate and not args.delete:
        print("Error: --regenerate requires --delete")
        sys.exit(1)

    meaning_ids = None
    if args.meaning_ids:
        meaning_ids = [int(x.strip()) for x in args.meaning_ids.split(",")]

    print("=" * 60)
    print("Compound Word Example Fixer")
    print("=" * 60)

    # Find bad examples
    bad_examples = find_compound_only_examples(
        max_examples=args.max_examples,
        meaning_ids=meaning_ids,
    )

    if not bad_examples:
        print("\nNo compound-only examples found!")
        return

    print(f"\nFound {len(bad_examples)} examples where word only appears in compounds:\n")

    # Group by meaning for clearer output
    by_meaning = {}
    for ex in bad_examples:
        if ex['meaning_id'] not in by_meaning:
            by_meaning[ex['meaning_id']] = []
        by_meaning[ex['meaning_id']].append(ex)

    for meaning_id, examples in by_meaning.items():
        word = examples[0]['word']
        print(f"Word: '{word}' (meaning_id: {meaning_id})")
        for ex in examples:
            issue = ex.get('issue_type', 'unknown')
            print(f"  - ID {ex['id']} [{issue}]: \"{ex['sentence']}\"")
            if ex.get('compounds'):
                print(f"    Compounds found: {ex['compounds']}")
        print()

    affected_meaning_ids = list(by_meaning.keys())

    if args.dry_run:
        print("Dry run complete. Use --delete to remove these examples.")
        return

    if args.delete:
        print("\nDeleting bad examples...")
        example_ids = [ex['id'] for ex in bad_examples]
        deleted, linked = delete_examples(example_ids)
        print(f"  Deleted: {deleted} examples")
        if linked:
            print(f"  Preserved (linked to bookmarks): {linked} examples")

    if args.regenerate:
        print("\nRegenerating examples for affected meanings...")
        regenerated = regenerate_examples_for_meanings(affected_meaning_ids)
        print(f"\nRegenerated {regenerated} new examples")

    print("\nDone!")


if __name__ == "__main__":
    main()
