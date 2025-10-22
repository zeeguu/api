#!/usr/bin/env python

"""
Migration script to recalculate ranks for ALL single-word phrases.

This updates phrase ranks based on the latest wordstats data.
Run this after updating the wordstats package with new word frequency data.
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from wordstats import Word
from zeeguu.core.model import db
from zeeguu.core.model.phrase import Phrase

# Initialize Flask app
from zeeguu.api.app import create_app

app = create_app()

IMPOSSIBLE_RANK = 1000000

def recalculate_single_word_phrase_ranks():
    """Recalculate ranks for ALL single-word phrases."""

    # Find all phrases with single words (no spaces)
    single_word_phrases = Phrase.query.filter(
        ~Phrase.content.like('% %'),  # Does NOT contain a space
    ).all()

    print(f"Found {len(single_word_phrases)} single-word phrases")

    updated_count = 0
    unchanged_count = 0
    errors_count = 0

    for i, phrase in enumerate(single_word_phrases):
        if (i + 1) % 10000 == 0:
            print(f"Processed {i + 1}/{len(single_word_phrases)} phrases...")
            db.session.commit()  # Commit in batches

        try:
            # Get the current rank from wordstats
            try:
                rank = Word.stats(phrase.content, phrase.language.code).rank
                if rank is None:
                    rank = IMPOSSIBLE_RANK
            except FileNotFoundError:
                # Language not supported in wordstats
                rank = None
            except Exception:
                # Word not found in wordstats
                rank = IMPOSSIBLE_RANK

            if rank is not None and phrase.rank != rank:
                old_rank = phrase.rank
                phrase.rank = rank
                db.session.add(phrase)
                updated_count += 1

                if updated_count <= 20:  # Show first 20 changes
                    print(f"  Updated '{phrase.content}' ({phrase.language.code}): {old_rank} -> {rank}")
            else:
                unchanged_count += 1

        except Exception as e:
            print(f"Error processing '{phrase.content}': {e}")
            errors_count += 1
            continue

    # Final commit
    try:
        db.session.commit()
        print(f"\nSummary:")
        print(f"  Updated: {updated_count} phrases")
        print(f"  Unchanged: {unchanged_count} phrases")
        print(f"  Errors: {errors_count} phrases")
        print(f"  Total processed: {len(single_word_phrases)} phrases")
    except Exception as e:
        db.session.rollback()
        print(f"Error committing changes: {e}")
        return False

    return True

if __name__ == "__main__":
    print("Starting single-word phrase rank recalculation...")
    print("This will update ranks based on the latest wordstats data.\n")

    with app.app_context():
        success = recalculate_single_word_phrase_ranks()
        if success:
            print("\nMigration completed successfully!")
        else:
            print("\nMigration failed!")
            sys.exit(1)
