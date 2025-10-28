#!/usr/bin/env python3
"""
Script to validate existing example sentences and remove those that use wrong meanings.
Batches multiple examples together for efficient LLM validation.
"""

import os
import sys
import json
import time
from typing import List, Dict, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import zeeguu.core.model

db_session = zeeguu.core.model.db.session


from zeeguu.core.model import ExampleSentence, Meaning, Phrase
from zeeguu.logging import log
import anthropic

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()


# Batch size for LLM validation (balance between efficiency and token limits)
BATCH_SIZE = 20


def get_anthropic_client():
    """Initialize Anthropic client"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    return anthropic.Anthropic(api_key=api_key)


def validate_examples_batch(client, examples_batch: List[Dict]) -> Set[int]:
    """
    Send a batch of examples to LLM for validation.
    Returns set of example IDs that use the WRONG meaning.
    """

    # Prepare the validation prompt
    examples_text = json.dumps(examples_batch, indent=2)

    prompt = f"""Analyze these example sentences for language learning. Each example has:
- id: unique identifier
- word: the word being taught
- translation: the intended meaning/translation
- sentence: example sentence in source language
- sentence_translation: translation of the example

Your task: Identify examples where the word is used with a DIFFERENT meaning than the provided translation.

Examples to analyze:
{examples_text}

Return ONLY a JSON array of IDs for examples that use the WRONG meaning.
If all examples are correct, return an empty array: []

For instance, if word="virker" and translation="seem", but the sentence uses "virker" to mean "work/function", that ID should be included.

Response format - ONLY return the JSON array, nothing else:
[id1, id2, id3]

Or if all are correct:
[]"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=500,
            temperature=0,
            system="You are a language expert validating example sentences for language learning. Return only JSON arrays with no additional text.",
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse the response
        content = response.content[0].text.strip()

        # Log raw response for debugging
        if len(content) > 500:
            log(f"Warning: Long response ({len(content)} chars)")

        # Clean up potential markdown formatting
        if "```json" in content.lower():
            start = content.lower().find("```json") + 7
            end = content.find("```", start)
            if end != -1:
                content = content[start:end]
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end != -1:
                content = content[start:end]

        # Remove any non-JSON text before/after the array
        content = content.strip()

        # Find the JSON array
        start_idx = content.find("[")
        end_idx = content.rfind("]")

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_content = content[start_idx : end_idx + 1]
        else:
            # No array found, assume all examples are correct
            log(f"No JSON array found in response: {content[:100]}")
            return set()

        # Parse JSON array
        try:
            wrong_ids = json.loads(json_content)
            if not isinstance(wrong_ids, list):
                log(f"Response is not a list: {wrong_ids}")
                return set()
            return set(wrong_ids)
        except json.JSONDecodeError as e:
            log(f"Failed to parse JSON: {e}")
            log(f"Content was: {json_content[:200]}")
            return set()

    except Exception as e:
        log(f"Error validating batch: {e}")
        return set()


def main():
    """Main function to validate and clean examples"""

    print("Starting validation of example sentences...")
    print("=" * 60)

    # Get total count
    total_count = db_session.query(ExampleSentence).count()
    print(f"Total example sentences in database: {total_count}")

    # Get all examples with their meanings
    query = (
        db_session.query(
            ExampleSentence.id,
            ExampleSentence.sentence,
            ExampleSentence.translation,
            Phrase.content.label("word"),
            Phrase.language_id,
        )
        .join(Meaning, ExampleSentence.meaning_id == Meaning.id)
        .join(Phrase, Meaning.origin_id == Phrase.id)
    )

    # Also get the translation
    translation_subquery = (
        db_session.query(
            Meaning.id.label("meaning_id"), Phrase.content.label("translation_word")
        ).join(Phrase, Meaning.translation_id == Phrase.id)
    ).subquery()

    examples = (
        query.join(
            translation_subquery,
            ExampleSentence.meaning_id == translation_subquery.c.meaning_id,
        )
        .add_column(translation_subquery.c.translation_word)
        .all()
    )

    print(f"Retrieved {len(examples)} examples for validation")

    # Initialize Anthropic client
    client = get_anthropic_client()

    # Import needed for checking bookmarks
    from zeeguu.core.model import ExampleSentenceContext

    # Process in batches
    all_wrong_ids = set()
    all_deleted_ids = set()
    all_linked_ids = set()

    for i in range(0, len(examples), BATCH_SIZE):
        batch_examples = examples[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(examples) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\nProcessing batch {batch_num}/{total_batches}...")

        # Prepare batch for validation
        batch_data = []
        batch_lookup = {}  # Map ID to full example data
        for ex in batch_examples:
            batch_data.append(
                {
                    "id": ex.id,
                    "word": ex.word,
                    "translation": ex.translation_word,
                    "sentence": ex.sentence,
                    "sentence_translation": ex.translation,
                }
            )
            batch_lookup[ex.id] = ex

        # Validate this batch with retry logic for rate limits
        retry_count = 0
        max_retries = 3
        wrong_ids = set()

        while retry_count < max_retries:
            try:
                wrong_ids = validate_examples_batch(client, batch_data)
                break  # Success, exit retry loop
            except Exception as e:
                if "rate_limit_error" in str(e) or "429" in str(e):
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 60 * retry_count  # Wait 60s, 120s, 180s
                        print(
                            f"  Rate limited. Waiting {wait_time} seconds before retry {retry_count}/{max_retries}..."
                        )
                        time.sleep(wait_time)
                    else:
                        print(
                            f"  Skipping batch after {max_retries} rate limit retries"
                        )
                        wrong_ids = set()
                else:
                    # Not a rate limit error, treat as validation failure
                    wrong_ids = set()
                    break

        if wrong_ids:
            print(f"  Found {len(wrong_ids)} incorrect examples")
            all_wrong_ids.update(wrong_ids)

            # Check which ones are linked to bookmarks
            linked_in_batch = set(
                row[0]
                for row in db_session.query(ExampleSentenceContext.example_sentence_id)
                .filter(ExampleSentenceContext.example_sentence_id.in_(wrong_ids))
                .all()
            )

            deletable_in_batch = wrong_ids - linked_in_batch

            # Print details of incorrect examples before deleting
            for wrong_id in wrong_ids:
                if wrong_id in batch_lookup:
                    ex = batch_lookup[wrong_id]
                    print(f"    ID {ex.id}: '{ex.word}' → '{ex.translation_word}'")
                    print(f"      Sentence: {ex.sentence}")
                    if wrong_id in linked_in_batch:
                        print(f"      ⚠️  SKIPPED - linked to bookmark")
                        all_linked_ids.add(wrong_id)
                    else:
                        print(f"      ✗ DELETING - uses wrong meaning")

            # Delete the incorrect examples that aren't linked
            if deletable_in_batch:
                deleted_count = (
                    db_session.query(ExampleSentence)
                    .filter(ExampleSentence.id.in_(deletable_in_batch))
                    .delete(synchronize_session=False)
                )
                db_session.commit()
                all_deleted_ids.update(deletable_in_batch)
                print(f"  ✓ Deleted {deleted_count} incorrect examples")
        else:
            print(f"  All examples in this batch are correct")

        # Add a small delay between batches to avoid rate limits
        if i + BATCH_SIZE < len(examples):  # Don't delay after the last batch
            time.sleep(10)

    print("\n" + "=" * 60)
    print(f"Validation and cleanup complete!")
    print(f"\nSummary:")
    print(f"  Total incorrect examples found: {len(all_wrong_ids)}")
    print(f"  ✓ Deleted: {len(all_deleted_ids)} examples")
    print(f"  ⚠️  Preserved (linked to bookmarks): {len(all_linked_ids)} examples")

    if all_linked_ids:
        print(
            f"\nExamples that couldn't be deleted (linked to bookmarks): {sorted(all_linked_ids)}"
        )

    if all_deleted_ids:
        # Count affected meanings
        print(f"\nNext steps:")
        print(
            f"1. Run the prefetch script to regenerate examples for affected meanings"
        )
        print(f"2. New examples will use the v3 prompt which prevents wrong meanings")
    elif all_wrong_ids:
        print(
            f"\nAll incorrect examples are linked to bookmarks and couldn't be deleted."
        )
        print(
            f"Consider manually updating these bookmarks or regenerating the examples."
        )
    else:
        print("\nAll examples appear to be using the correct meanings!")


if __name__ == "__main__":
    main()
