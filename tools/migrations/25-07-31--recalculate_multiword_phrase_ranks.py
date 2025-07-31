#!/usr/bin/env python

"""
Migration script to recalculate ranks for existing multi-word phrases.

This script finds all phrases with multiple words that have rank=NULL
and recalculates their rank based on the hardest (least frequent) component word.
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

def recalculate_multiword_phrase_ranks():
    """Recalculate ranks for multi-word phrases that currently have rank=NULL."""
    
    # Find all phrases with multiple words and NULL rank
    multiword_phrases = Phrase.query.filter(
        Phrase.content.like('% %'),  # Contains at least one space
        Phrase.rank == None
    ).all()
    
    print(f"Found {len(multiword_phrases)} multi-word phrases with NULL rank")
    
    updated_count = 0
    
    for phrase in multiword_phrases:
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
                    new_rank = max(ranks)
                    phrase.rank = new_rank
                    db.session.add(phrase)
                    updated_count += 1
                    if updated_count % 1000 == 0:
                        print(f"Updated {updated_count} phrases so far...")
            except Exception as e:
                print(f"Error processing '{phrase.content}': {e}")
                continue
    
    # Commit all changes
    try:
        db.session.commit()
        print(f"Successfully updated {updated_count} multi-word phrases")
    except Exception as e:
        db.session.rollback()
        print(f"Error committing changes: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Starting multi-word phrase rank recalculation...")
    with app.app_context():
        success = recalculate_multiword_phrase_ranks()
        if success:
            print("Migration completed successfully!")
        else:
            print("Migration failed!")
            sys.exit(1)