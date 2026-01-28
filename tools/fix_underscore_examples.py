#!/usr/bin/env python3
"""
Script to fix example sentences with underscore formatting issues.

This fixes examples where the LLM generated compound words with underscores
like "Bolig_forhold_" instead of "Boligforhold" or used markdown-style
emphasis like "__word__".

Usage:
    # Dry run - show what would be fixed
    python -m tools.fix_underscore_examples --dry-run

    # Delete bad examples and regenerate new ones
    python -m tools.fix_underscore_examples --fix
"""

import argparse
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import ExampleSentence, Meaning, Phrase, Language
from zeeguu.core.model.example_sentence_context import ExampleSentenceContext
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.logging import log


def find_underscore_examples():
    """
    Find examples with underscore formatting issues.

    Patterns detected:
    - Compound underscores: Prefix_word_ (like Bolig_forhold_)
    - Markdown emphasis: __word__
    """
    query = db.session.query(
        ExampleSentence.id,
        ExampleSentence.sentence,
        ExampleSentence.meaning_id,
        Phrase.content.label('word'),
        Language.code.label('lang_code'),
    ).join(Meaning, ExampleSentence.meaning_id == Meaning.id
    ).join(Phrase, Meaning.origin_id == Phrase.id
    ).join(Language, Phrase.language_id == Language.id)

    results = query.all()
    bad_examples = []

    for r in results:
        word = r.word
        if len(word) < 2:
            continue

        # Pattern 1: Compound underscores like Prefix_word_ or _word_Suffix
        pattern1 = rf'\w+_{re.escape(word)}_'
        pattern2 = rf'_{re.escape(word)}_\w*'

        # Pattern 2: Markdown emphasis like __word__
        pattern3 = rf'__{re.escape(word)}__'

        issue_type = None
        if re.search(pattern1, r.sentence, re.IGNORECASE):
            issue_type = 'compound_underscore'
        elif re.search(pattern2, r.sentence, re.IGNORECASE):
            issue_type = 'compound_underscore'
        elif re.search(pattern3, r.sentence, re.IGNORECASE):
            issue_type = 'markdown_emphasis'

        if issue_type:
            bad_examples.append({
                'id': r.id,
                'sentence': r.sentence,
                'word': r.word,
                'meaning_id': r.meaning_id,
                'lang_code': r.lang_code,
                'issue_type': issue_type,
            })

    return bad_examples


def delete_examples(example_ids):
    """Delete examples by ID, returning count of deleted and skipped (linked to bookmarks)."""
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

    deleted_count = 0
    if deletable_ids:
        deleted_count = (
            db.session.query(ExampleSentence)
            .filter(ExampleSentence.id.in_(deletable_ids))
            .delete(synchronize_session=False)
        )
        db.session.commit()

    return deleted_count, len(linked_ids)


def regenerate_examples_for_meaning(meaning_id, target_count=5):
    """Regenerate examples for a specific meaning."""
    from zeeguu.core.llm_services import get_llm_service

    meaning = Meaning.query.get(meaning_id)
    if not meaning:
        print(f"  Warning: Meaning {meaning_id} not found")
        return 0

    # Check current count
    existing_count = ExampleSentence.query.filter(
        ExampleSentence.meaning_id == meaning_id
    ).count()

    examples_to_generate = max(0, target_count - existing_count)
    if examples_to_generate == 0:
        print(f"  Meaning {meaning_id} already has {existing_count} examples")
        return 0

    origin_word = meaning.origin.content
    translation = meaning.translation.content
    origin_lang = meaning.origin.language.code
    translation_lang = meaning.translation.language.code

    print(f"  Generating {examples_to_generate} examples for '{origin_word}' -> '{translation}'...")

    try:
        llm_service = get_llm_service()
        examples = llm_service.generate_examples(
            word=origin_word,
            translation=translation,
            source_lang=origin_lang,
            target_lang=translation_lang,
            cefr_level="B1",
            prompt_version="v3",
            count=examples_to_generate,
        )

        llm_model = examples[0]["llm_model"] if examples else "unknown"
        prompt_version = examples[0]["prompt_version"] if examples else "v3"

        ai_generator = AIGenerator.find_or_create(
            db.session,
            llm_model,
            prompt_version,
            description="Regenerated after underscore fix",
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
        print(f"    Created {len(examples)} new examples")
        return len(examples)

    except Exception as e:
        print(f"    Error: {e}")
        db.session.rollback()
        return 0


def main():
    parser = argparse.ArgumentParser(description="Fix underscore formatting in examples")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be fixed")
    parser.add_argument("--fix", action="store_true", help="Delete bad examples and regenerate")
    args = parser.parse_args()

    if not args.dry_run and not args.fix:
        print("Error: Specify --dry-run or --fix")
        sys.exit(1)

    print("=" * 60)
    print("Underscore Example Fixer")
    print("=" * 60)

    # Find bad examples
    bad_examples = find_underscore_examples()

    if not bad_examples:
        print("\nNo underscore-formatted examples found!")
        return

    print(f"\nFound {len(bad_examples)} examples with underscore issues:\n")

    # Group by meaning
    by_meaning = {}
    for ex in bad_examples:
        if ex['meaning_id'] not in by_meaning:
            by_meaning[ex['meaning_id']] = []
        by_meaning[ex['meaning_id']].append(ex)

    for meaning_id, examples in by_meaning.items():
        word = examples[0]['word']
        lang = examples[0]['lang_code']
        print(f"Word: '{word}' [{lang}] (meaning_id: {meaning_id})")
        for ex in examples:
            print(f"  - ID {ex['id']} [{ex['issue_type']}]:")
            print(f"    \"{ex['sentence']}\"")
        print()

    if args.dry_run:
        print("Dry run complete. Use --fix to delete and regenerate.")
        return

    # Delete bad examples
    print("Deleting bad examples...")
    example_ids = [ex['id'] for ex in bad_examples]
    deleted, linked = delete_examples(example_ids)
    print(f"  Deleted: {deleted}")
    if linked:
        print(f"  Skipped (linked to bookmarks): {linked}")

    # Regenerate for affected meanings
    print("\nRegenerating examples...")
    total_regenerated = 0
    for meaning_id in by_meaning.keys():
        regenerated = regenerate_examples_for_meaning(meaning_id)
        total_regenerated += regenerated

    print(f"\nDone! Regenerated {total_regenerated} new examples.")


if __name__ == "__main__":
    main()
