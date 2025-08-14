#!/usr/bin/env python

"""
Comprehensive script to recalculate ranks for ALL words in the database.

This script will:
1. Recalculate ranks for all single-word phrases that have missing or incorrect ranks
2. Recalculate ranks for all multi-word phrases based on their component words
3. Handle language-specific word frequency data availability
4. Provide detailed progress reporting

Usage:
    source ~/.venvs/z_env/bin/activate && python tools/recalculate_all_word_ranks.py
"""

import sys
import os
from datetime import datetime

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from wordstats import Word
from zeeguu.core.model import db
from zeeguu.core.model.phrase import Phrase

# Initialize Flask app
from zeeguu.api.app import create_app

app = create_app()

IMPOSSIBLE_RANK = 1000000
BATCH_SIZE = 1000

def recalculate_single_word_ranks():
    """Recalculate ranks for single-word phrases."""
    print("\n=== RECALCULATING SINGLE-WORD PHRASE RANKS ===")
    
    # Find all single-word phrases (no spaces)
    single_word_phrases = Phrase.query.filter(
        ~Phrase.content.like('% %')  # Does not contain spaces
    ).all()
    
    print(f"Found {len(single_word_phrases)} single-word phrases to process")
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    unsupported_languages = set()
    
    for i, phrase in enumerate(single_word_phrases):
        try:
            # Get rank from wordstats
            word_stats = Word.stats(phrase.content, phrase.language.code)
            new_rank = word_stats.rank
            
            # Skip if rank is the default "unknown" value
            if new_rank == 100000 or new_rank is None:
                skipped_count += 1
                continue
            
            # Update the phrase rank if it's different
            if phrase.rank != new_rank:
                phrase.rank = new_rank
                db.session.add(phrase)
                updated_count += 1
            
            # Batch commit every BATCH_SIZE records
            if (i + 1) % BATCH_SIZE == 0:
                db.session.commit()
                print(f"  Processed {i + 1}/{len(single_word_phrases)} - Updated: {updated_count}, Skipped: {skipped_count}, Errors: {error_count}")
                
        except FileNotFoundError as e:
            # Language not supported by wordstats
            import re
            res = re.search(r'/(\w+)_50k\.txt', str(e))
            if res and res.group(1) not in unsupported_languages:
                unsupported_languages.add(res.group(1))
                print(f"  Unsupported language detected: {res.group(1)}")
            skipped_count += 1
            
        except Exception as e:
            error_count += 1
            if error_count < 10:  # Only print first 10 errors
                print(f"  Error processing '{phrase.content}' ({phrase.language.code}): {e}")
    
    # Final commit
    try:
        db.session.commit()
        print(f"Single-word phrases: Updated {updated_count}, Skipped {skipped_count}, Errors {error_count}")
        if unsupported_languages:
            print(f"Unsupported languages: {', '.join(sorted(unsupported_languages))}")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error committing single-word changes: {e}")
        return False

def recalculate_multiword_phrase_ranks():
    """Recalculate ranks for multi-word phrases."""
    print("\n=== RECALCULATING MULTI-WORD PHRASE RANKS ===")
    
    # Find all multi-word phrases (contain spaces)
    multiword_phrases = Phrase.query.filter(
        Phrase.content.like('% %')  # Contains at least one space
    ).all()
    
    print(f"Found {len(multiword_phrases)} multi-word phrases to process")
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    for i, phrase in enumerate(multiword_phrases):
        try:
            words = phrase.content.split()
            if len(words) <= 1:
                continue
                
            ranks = []
            for single_word in words:
                try:
                    word_stats = Word.stats(single_word, phrase.language.code)
                    if word_stats.rank is not None and word_stats.rank != 100000:
                        ranks.append(word_stats.rank)
                except:
                    # If we can't get rank for a word, treat it as very rare
                    ranks.append(IMPOSSIBLE_RANK)
            
            if ranks:
                # Take the highest rank (least frequent word) as phrase difficulty
                new_rank = max(ranks)
                
                # Update if different
                if phrase.rank != new_rank:
                    phrase.rank = new_rank
                    db.session.add(phrase)
                    updated_count += 1
            else:
                # No valid component ranks found
                if phrase.rank != IMPOSSIBLE_RANK:
                    phrase.rank = IMPOSSIBLE_RANK
                    db.session.add(phrase)
                    updated_count += 1
            
            # Batch commit every BATCH_SIZE records
            if (i + 1) % BATCH_SIZE == 0:
                db.session.commit()
                print(f"  Processed {i + 1}/{len(multiword_phrases)} - Updated: {updated_count}")
                
        except Exception as e:
            error_count += 1
            if error_count < 10:  # Only print first 10 errors
                print(f"  Error processing '{phrase.content}' ({phrase.language.code}): {e}")
    
    # Final commit
    try:
        db.session.commit()
        print(f"Multi-word phrases: Updated {updated_count}, Errors {error_count}")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error committing multi-word changes: {e}")
        return False

def print_sample_rankings():
    """Print some sample rankings to verify the recalculation worked."""
    print("\n=== SAMPLE RANKINGS AFTER RECALCULATION ===")
    
    # Get some common Danish words to check
    sample_words = ['skulle', 'have', 'være', 'den', 'det', 'en', 'at', 'for']
    
    for word_content in sample_words:
        phrase = Phrase.query.filter_by(content=word_content).first()
        if phrase:
            print(f"  '{phrase.content}' ({phrase.language.code}): rank {phrase.rank}")
        else:
            print(f"  '{word_content}': not found in database")

if __name__ == "__main__":
    print(f"Starting comprehensive word rank recalculation at {datetime.now()}")
    print("This may take several minutes depending on database size...")
    
    with app.app_context():
        success = True
        
        # Step 1: Recalculate single-word ranks
        if not recalculate_single_word_ranks():
            success = False
        
        # Step 2: Recalculate multi-word phrase ranks
        if success and not recalculate_multiword_phrase_ranks():
            success = False
        
        if success:
            print_sample_rankings()
            print(f"\n✅ Rank recalculation completed successfully at {datetime.now()}")
        else:
            print(f"\n❌ Rank recalculation failed at {datetime.now()}")
            sys.exit(1)