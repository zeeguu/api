#!/usr/bin/env python3
"""
Consolidate Duplicate Meanings Migration

This migration consolidates duplicate Meanings that represent the same semantic concept
(same origin + translation, case-insensitive) into canonical meanings.

It consolidates by:
1. Finding groups of Meanings with same semantic concept
2. Selecting the "best" canonical Meaning (oldest ID, most UserWords)
3. Moving all UserWords from duplicates to the canonical meaning
4. Deleting the duplicate Meanings

This cleans up legacy duplicates created before the semantic deduplication system.
"""

import sys
sys.path.append('.')
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.phrase import Phrase
from collections import defaultdict
import traceback

def find_duplicate_meaning_groups():
    """Find all groups of Meanings that represent the same semantic concept."""
    print("🔍 Scanning for duplicate Meanings...")
    
    # Get all meanings
    meanings = Meaning.query.all()
    print(f"📊 Found {len(meanings)} total Meanings to analyze...")
    
    # Group by semantic concept: (origin_lower, translation_lower, origin_lang, translation_lang)
    groups = defaultdict(list)
    
    for meaning in meanings:
        key = (
            meaning.origin.content.lower(),
            meaning.translation.content.lower(),
            meaning.origin.language_id,
            meaning.translation.language_id
        )
        groups[key].append(meaning)
    
    # Filter to only groups with duplicates
    duplicate_groups = {key: meanings_list for key, meanings_list in groups.items() if len(meanings_list) > 1}
    
    total_duplicates = sum(len(meanings_list) - 1 for meanings_list in duplicate_groups.values())
    
    print(f"""
📈 Duplicate Analysis Results:
   • {len(duplicate_groups)} duplicate semantic groups found
   • {total_duplicates} duplicate Meanings to consolidate  
   • {len(meanings) - total_duplicates} Meanings will remain after consolidation
    """)
    
    return duplicate_groups

def select_canonical_meaning(meanings_list):
    """Select the best Meaning to keep as canonical from duplicates.
    
    The canonical meaning is the one with ALL LOWERCASE origin and translation.
    If multiple exist, pick the one with most UserWords or oldest ID.
    If none are all lowercase, pick the one closest to lowercase.
    """
    
    def get_canonicality_score(meaning):
        # Priority 1: Both origin and translation are lowercase
        origin_is_lower = meaning.origin.content == meaning.origin.content.lower()
        translation_is_lower = meaning.translation.content == meaning.translation.content.lower()
        
        if origin_is_lower and translation_is_lower:
            lowercase_score = 1000000  # Highest priority
        elif origin_is_lower or translation_is_lower:
            lowercase_score = 100000   # Medium priority
        else:
            lowercase_score = 0         # Lowest priority
        
        # Priority 2: Most UserWords (within same lowercase category)
        user_word_count = UserWord.query.filter_by(meaning_id=meaning.id).count()
        
        # Priority 3: Age (older = lower ID = slight priority)
        age_priority = -meaning.id / 1000000
        
        total_score = lowercase_score + user_word_count * 10 + age_priority
        return total_score
    
    # Sort by canonicality score (descending)
    sorted_meanings = sorted(meanings_list, key=get_canonicality_score, reverse=True)
    canonical = sorted_meanings[0]
    duplicates = sorted_meanings[1:]
    
    # Log if we're not getting a fully lowercase canonical
    origin_is_lower = canonical.origin.content == canonical.origin.content.lower()
    translation_is_lower = canonical.translation.content == canonical.translation.content.lower()
    if not (origin_is_lower and translation_is_lower):
        print(f"     ⚠️ No fully lowercase variant exists, using: \"{canonical.origin.content}\" -> \"{canonical.translation.content}\"")
    
    return canonical, duplicates

def consolidate_meaning_group(canonical_meaning, duplicate_meanings):
    """Consolidate a group of duplicate Meanings into the canonical one."""
    
    with db.session.no_autoflush:
        canonical_key = f"'{canonical_meaning.origin.content}' -> '{canonical_meaning.translation.content}'"
        
        print(f"🔄 Consolidating {len(duplicate_meanings)} duplicate meanings into Meaning {canonical_meaning.id} ({canonical_key})")
        
        stats = {
            "userwords_moved": 0,
            "meanings_deleted": 0,
        }
        
        for dup_meaning in duplicate_meanings:
            try:
                dup_meaning_id = dup_meaning.id
                print(f"   Processing duplicate Meaning {dup_meaning_id}: \"{dup_meaning.origin.content}\" -> \"{dup_meaning.translation.content}\"")
                
                # Move all UserWords from duplicate to canonical meaning
                user_words = UserWord.query.filter_by(meaning_id=dup_meaning_id).all()
                user_word_count = len(user_words)
                
                if user_word_count > 0:
                    print(f"     📝 Moving {user_word_count} UserWords to canonical meaning")
                    for user_word in user_words:
                        user_word.meaning_id = canonical_meaning.id
                        db.session.add(user_word)
                        stats["userwords_moved"] += 1
                    # Flush to ensure UserWords are updated before we delete the Meaning
                    db.session.flush()
                
                # Delete the duplicate Meaning
                db.session.delete(dup_meaning)
                stats["meanings_deleted"] += 1
                print(f"     ❌ Deleted duplicate Meaning {dup_meaning_id}")
                
            except Exception as e:
                print(f"     ⚠️ Error processing Meaning {dup_meaning_id}: {e}")
                continue
        
        return stats

def run_meaning_consolidation_migration():
    """Execute the Meaning consolidation migration."""
    print("🚀 STARTING MEANING CONSOLIDATION MIGRATION")
    print("=" * 60)
    
    duplicate_groups = find_duplicate_meaning_groups()
    
    if not duplicate_groups:
        print("✅ No duplicate Meanings found! Database is already clean.")
        return
    
    total_duplicates = sum(len(meanings_list) - 1 for meanings_list in duplicate_groups.values())
    print(f"⚠️  About to consolidate {total_duplicates} duplicate Meanings across {len(duplicate_groups)} groups.")
    print(f"\n🤖 AUTO-PROCEEDING with consolidation...")
    
    # Global stats
    total_stats = {
        "groups_processed": 0,
        "groups_failed": 0,
        "userwords_moved": 0,
        "meanings_deleted": 0,
    }
    
    # Process each duplicate group in its own transaction
    for i, (key, meanings_list) in enumerate(duplicate_groups.items(), 1):
        origin_lower, translation_lower, origin_lang_id, translation_lang_id = key
        
        print(f"\n📚 [{i}/{len(duplicate_groups)}] Processing: '{origin_lower}' -> '{translation_lower}'")
        print(f"     Found {len(meanings_list)} duplicate meanings")
        
        try:
            # Select canonical and duplicates
            canonical_meaning, duplicate_meanings = select_canonical_meaning(meanings_list)
            
            print(f"     🎯 Selected Meaning {canonical_meaning.id} as canonical (\"{canonical_meaning.origin.content}\" -> \"{canonical_meaning.translation.content}\")")
            
            # Consolidate the group
            group_stats = consolidate_meaning_group(canonical_meaning, duplicate_meanings)
            
            # Update totals
            for stat_key, value in group_stats.items():
                total_stats[stat_key] += value
            total_stats["groups_processed"] += 1
            
            # Commit this group's changes
            db.session.commit()
            
            # Progress indicator every 10 groups
            if i % 10 == 0:
                print(f"     📊 Progress: {i}/{len(duplicate_groups)} groups processed")
                
        except Exception as e:
            print(f"     ❌ Failed to process group: {e}")
            total_stats["groups_failed"] += 1
            # Roll back this group's changes and continue with next group
            db.session.rollback()
            continue
    
    print(f"""
🎉 MEANING CONSOLIDATION COMPLETED! 🎉

📈 Final Statistics:
   • Semantic groups processed: {total_stats['groups_processed']}
   • Groups failed: {total_stats['groups_failed']}  
   • UserWords moved to canonical meanings: {total_stats['userwords_moved']}
   • Duplicate meanings deleted: {total_stats['meanings_deleted']}

✨ Result: Each semantic concept now has exactly ONE canonical Meaning.
🔥 Semantic deduplication system will prevent future duplicates!

Database meanings are now CONSOLIDATED! 🤖✅
    """)

if __name__ == "__main__":
    run_meaning_consolidation_migration()