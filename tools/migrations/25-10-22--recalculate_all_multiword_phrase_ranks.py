#!/usr/bin/env python

"""
Migration script to recalculate ranks for ALL multi-word phrases.

This fixes phrases that were created before the July 31, 2025 fix
and have incorrect ranks (using most frequent word instead of least frequent).
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

def recalculate_all_multiword_phrase_ranks():
    """Recalculate ranks for ALL multi-word phrases."""

    # Find all phrases with multiple words
    multiword_phrases = Phrase.query.filter(
        Phrase.content.like('% %'),  # Contains at least one space
    ).all()

    print(f"Found {len(multiword_phrases)} multi-word phrases")

    updated_count = 0
    unchanged_count = 0

    for i, phrase in enumerate(multiword_phrases):
        if (i + 1) % 10000 == 0:
            print(f"Processed {i + 1}/{len(multiword_phrases)} phrases...")
            db.session.commit()  # Commit in batches

        words = phrase.content.split()
        if len(words) > 1:
            try:
                ranks = []
                for single_word in words:
                    try:
                        rank = Word.stats(single_word, phrase.language.code).rank
                        if rank is not None:
                            ranks.append(rank)
                    except:
                        # If we can't get rank for a word, treat it as very rare
                        ranks.append(IMPOSSIBLE_RANK)

                if ranks:
                    # Take the highest rank (least frequent word)
                    correct_rank = max(ranks)

                    if phrase.rank != correct_rank:
                        old_rank = phrase.rank
                        phrase.rank = correct_rank
                        db.session.add(phrase)
                        updated_count += 1

                        if updated_count <= 10:  # Show first 10 changes
                            print(f"  Updated '{phrase.content}': {old_rank} -> {correct_rank}")
                    else:
                        unchanged_count += 1

            except Exception as e:
                print(f"Error processing '{phrase.content}': {e}")
                continue

    # Final commit
    try:
        db.session.commit()
        print(f"\nSummary:")
        print(f"  Updated: {updated_count} phrases")
        print(f"  Unchanged: {unchanged_count} phrases")
        print(f"  Total processed: {len(multiword_phrases)} phrases")
    except Exception as e:
        db.session.rollback()
        print(f"Error committing changes: {e}")
        return False

    return True

if __name__ == "__main__":
    print("Starting ALL multi-word phrase rank recalculation...")
    print("This will fix phrases created before the July 31, 2025 fix.\n")

    with app.app_context():
        success = recalculate_all_multiword_phrase_ranks()
        if success:
            print("\nMigration completed successfully!")
        else:
            print("\nMigration failed!")
            sys.exit(1)
