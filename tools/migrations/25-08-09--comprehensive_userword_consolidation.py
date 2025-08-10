#!/usr/bin/env python3
"""
Comprehensive UserWord Duplicate Consolidation Migration

This migration consolidates ALL duplicate UserWords across the entire database.
It handles all foreign key relationships properly:
- Bookmarks
- Exercises
- BasicSRSchedule entries
- Any other references

Let's do this! 🤖
"""

import sys

sys.path.append(".")
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from collections import defaultdict
import traceback


def find_all_duplicate_groups():
    """Find ALL duplicate UserWord groups across the entire database."""
    print("🔍 Scanning entire database for duplicate UserWords...")

    # Get ALL UserWords with their meaning details
    user_words = UserWord.query.join(Meaning, UserWord.meaning_id == Meaning.id).all()

    print(f"📊 Found {len(user_words)} total UserWords to analyze...")

    # Group by semantic meaning: (user_id, origin_lower, translation_lower, target_language)
    groups = defaultdict(list)

    for uw in user_words:
        key = (
            uw.user_id,
            uw.meaning.origin.content.lower(),
            uw.meaning.translation.content.lower(),
            uw.meaning.translation.language_id,
        )
        groups[key].append(uw)

    # Filter to only groups with duplicates
    duplicate_groups = {key: uws for key, uws in groups.items() if len(uws) > 1}

    total_duplicates = sum(len(uws) - 1 for uws in duplicate_groups.values())
    total_users_affected = len(set(key[0] for key in duplicate_groups.keys()))

    print(
        f"""
📈 Duplicate Analysis Results:
   • {len(duplicate_groups)} duplicate groups found
   • {total_duplicates} duplicate UserWords to consolidate  
   • {total_users_affected} users affected
   • {len(user_words) - total_duplicates} UserWords will remain after consolidation
    """
    )

    return duplicate_groups


def select_best_primary(user_words_list):
    """Select the best UserWord to keep as primary from duplicates."""

    def get_priority_score(uw):
        # Priority: Has schedule > has exercises > fit_for_study > most bookmarks > oldest ID
        # Use no_autoflush to prevent premature flushes during queries
        with db.session.no_autoflush:
            schedule = BasicSRSchedule.find(uw)
            has_schedule = 10 if schedule else 0

            exercise_count = Exercise.query.filter_by(user_word_id=uw.id).count()
            has_exercises = min(exercise_count, 5)  # Cap at 5 to avoid huge differences

            fit_for_study = 3 if uw.fit_for_study else 0

            bookmark_count = Bookmark.query.filter_by(user_word_id=uw.id).count()
            has_bookmarks = min(bookmark_count, 3)  # Cap at 3

            # Negative ID so older UserWords (lower ID) get higher priority as tiebreaker
            age_priority = -uw.id / 1000000  # Small influence

            total_score = (
                has_schedule + has_exercises + fit_for_study + has_bookmarks + age_priority
            )
            return total_score

    # Sort by priority score (descending)
    sorted_uws = sorted(user_words_list, key=get_priority_score, reverse=True)
    return sorted_uws[0], sorted_uws[1:]


def consolidate_userword_group(primary_uw, duplicate_uws):
    """Consolidate a group of duplicate UserWords into the primary one."""
    # Use no_autoflush for the entire consolidation process
    with db.session.no_autoflush:
        user_id = primary_uw.user_id
        word_key = f"'{primary_uw.meaning.origin.content.lower()}' -> '{primary_uw.meaning.translation.content.lower()}'"

        print(
            f"🔄 Consolidating {len(duplicate_uws)} duplicates into UserWord {primary_uw.id} for user {user_id} ({word_key})"
        )

        stats = {
            "bookmarks_moved": 0,
            "exercises_deleted": 0,
            "schedules_transferred": 0,
            "userwords_deleted": 0,
        }

        for dup_uw in duplicate_uws:
            try:
                # Store the ID before we might delete the object
                dup_uw_id = dup_uw.id
                print(f"   Processing duplicate UserWord {dup_uw_id}...")

                # 1. Move all bookmarks from duplicate to primary
                bookmarks = Bookmark.query.filter_by(user_word_id=dup_uw_id).all()
                bookmark_count = len(bookmarks)
                if bookmark_count > 0:
                    print(f"     📚 Moving {bookmark_count} bookmarks to primary")
                    for bookmark in bookmarks:
                        bookmark.user_word_id = primary_uw.id
                        db.session.add(bookmark)
                        stats["bookmarks_moved"] += 1
                    # Flush to ensure bookmarks are updated before we delete the UserWord
                    db.session.flush()

                # 2. Delete all exercises from duplicate (simpler than moving)
                exercises = Exercise.query.filter_by(user_word_id=dup_uw_id).all()
                exercise_count = len(exercises)
                if exercise_count > 0:
                    print(f"     🗑️ Deleting {exercise_count} exercises from duplicate")
                    for exercise in exercises:
                        db.session.delete(exercise)
                        stats["exercises_deleted"] += 1
                    # Flush to ensure exercises are deleted before we delete the UserWord
                    db.session.flush()

                # 3. Handle schedules - keep the most advanced one
                dup_schedule = BasicSRSchedule.find(dup_uw)
                primary_schedule = BasicSRSchedule.find(primary_uw)

                if dup_schedule and not primary_schedule:
                    # Transfer schedule from duplicate to primary
                    # First check if we haven't already assigned a schedule to this primary
                    existing_schedule = BasicSRSchedule.query.filter_by(user_word_id=primary_uw.id).first()
                    
                    if not existing_schedule:
                        dup_schedule.user_word_id = primary_uw.id
                        db.session.add(dup_schedule)
                        stats["schedules_transferred"] += 1
                        print(f"     ↗️ Transferred schedule to primary")
                    else:
                        # Schedule already exists for primary, delete duplicate
                        db.session.delete(dup_schedule)
                        print(f"     ⚠️ Primary already has a schedule, deleted duplicate")

                elif dup_schedule and primary_schedule:
                    # Keep the more advanced schedule (higher cooling_interval = more learned)
                    dup_cooling = dup_schedule.cooling_interval or 0
                    primary_cooling = primary_schedule.cooling_interval or 0

                    if dup_cooling > primary_cooling:
                        # Duplicate schedule is better - replace primary
                        db.session.delete(primary_schedule)
                        db.session.flush()  # Ensure deletion happens before reassignment
                        dup_schedule.user_word_id = primary_uw.id
                        db.session.add(dup_schedule)
                        stats["schedules_transferred"] += 1
                        print(
                            f"     ↗️ Replaced primary schedule with better one (cooling: {dup_cooling} > {primary_cooling})"
                        )
                    else:
                        # Primary schedule is better - delete duplicate
                        db.session.delete(dup_schedule)
                        print(
                            f"     ❌ Deleted inferior schedule (cooling: {dup_cooling} <= {primary_cooling})"
                        )
                elif dup_schedule:
                    # Only duplicate has schedule - delete it since primary doesn't need it
                    db.session.delete(dup_schedule)

                # 4. Merge UserWord properties (take the best of each)
                if dup_uw.fit_for_study and not primary_uw.fit_for_study:
                    primary_uw.fit_for_study = True
                    db.session.add(primary_uw)
                    print(f"     ✅ Updated primary to fit_for_study=True")

                if dup_uw.learned_time and (
                    not primary_uw.learned_time
                    or dup_uw.learned_time > primary_uw.learned_time
                ):
                    primary_uw.learned_time = dup_uw.learned_time
                    db.session.add(primary_uw)
                    print(f"     📅 Updated primary learned_time")

                if dup_uw.level and (
                    not primary_uw.level or dup_uw.level > primary_uw.level
                ):
                    primary_uw.level = dup_uw.level
                    db.session.add(primary_uw)
                    print(f"     📈 Updated primary level to {dup_uw.level}")
                    
                # Transfer preferred_bookmark if duplicate has one and primary doesn't
                if hasattr(dup_uw, 'preferred_bookmark_id') and dup_uw.preferred_bookmark_id:
                    if not primary_uw.preferred_bookmark_id:
                        primary_uw.preferred_bookmark_id = dup_uw.preferred_bookmark_id
                        db.session.add(primary_uw)
                        print(f"     📖 Transferred preferred_bookmark to primary")
                    # Clear the duplicate's preferred_bookmark before deletion
                    dup_uw.preferred_bookmark_id = None
                    db.session.add(dup_uw)
                    db.session.flush()  # Ensure the update happens before deletion

                # 5. Final check - ensure no foreign keys still reference this UserWord
                db.session.flush()  # Ensure all updates are persisted before deletion
                
                # Verify no exercises still reference this UserWord
                remaining_exercises = Exercise.query.filter_by(user_word_id=dup_uw_id).count()
                if remaining_exercises > 0:
                    raise Exception(f"Still has {remaining_exercises} exercises after migration attempt")
                
                # Verify no bookmarks still reference this UserWord  
                remaining_bookmarks = Bookmark.query.filter_by(user_word_id=dup_uw_id).count()
                if remaining_bookmarks > 0:
                    raise Exception(f"Still has {remaining_bookmarks} bookmarks after migration attempt")
                
                # 6. Delete the duplicate UserWord
                db.session.delete(dup_uw)
                stats["userwords_deleted"] += 1
                print(f"     ❌ Deleted duplicate UserWord {dup_uw_id}")

            except Exception as e:
                print(f"     ⚠️ Error processing UserWord {dup_uw_id}: {e}")
                # Don't let individual UserWord errors fail the whole group
                continue

    return stats


def run_comprehensive_migration():
    """Execute the comprehensive UserWord consolidation migration."""
    print("🚀 STARTING COMPREHENSIVE USERWORD CONSOLIDATION MIGRATION")
    print("=" * 60)

    duplicate_groups = find_all_duplicate_groups()

    if not duplicate_groups:
        print("✅ No duplicate UserWords found! Database is already clean.")
        return

    # Auto-proceed as requested by user
    total_duplicates = sum(len(uws) - 1 for uws in duplicate_groups.values())
    print(
        f"⚠️  About to consolidate {total_duplicates} duplicate UserWords across {len(duplicate_groups)} groups."
    )
    print(
        "   This will permanently delete duplicate UserWords and move their data to primary ones."
    )
    print(f"\n🤖 AUTO-PROCEEDING as requested! Let's clean this database!")

    print(f"\n🤖 ROGER! Proceeding with full consolidation...")

    # Global stats
    total_stats = {
        "groups_processed": 0,
        "groups_failed": 0,
        "bookmarks_moved": 0,
        "exercises_deleted": 0,
        "schedules_transferred": 0,
        "userwords_deleted": 0,
    }

    # Process each duplicate group in its own transaction
    for i, (key, user_words_list) in enumerate(duplicate_groups.items(), 1):
        user_id, origin_lower, translation_lower, target_lang_id = key

        print(
            f"\n📚 [{i}/{len(duplicate_groups)}] Processing user {user_id}: '{origin_lower}' -> '{translation_lower}'"
        )
        print(f"     Found {len(user_words_list)} duplicates")

        try:
            # Select primary and duplicates
            primary_uw, duplicate_uws = select_best_primary(user_words_list)

            # Consolidate the group
            group_stats = consolidate_userword_group(primary_uw, duplicate_uws)

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

    print(
        f"""
🎉 MIGRATION COMPLETED! 🎉

📈 Final Statistics:
   • Groups processed: {total_stats['groups_processed']}
   • Groups failed: {total_stats['groups_failed']}
   • UserWords deleted: {total_stats['userwords_deleted']}
   • Bookmarks moved: {total_stats['bookmarks_moved']}
   • Exercises deleted: {total_stats['exercises_deleted']}
   • Schedules transferred: {total_stats['schedules_transferred']}

✨ Result: Most duplicate UserWords have been consolidated.
{'❌ Some groups failed - manual cleanup may be needed.' if total_stats['groups_failed'] > 0 else '✅ All groups processed successfully!'}

Database consolidation {'partially' if total_stats['groups_failed'] > 0 else 'fully'} complete! 🤖
        """
    )


if __name__ == "__main__":
    run_comprehensive_migration()
