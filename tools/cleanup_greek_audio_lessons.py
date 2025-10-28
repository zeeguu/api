#!/usr/bin/env python
"""
Cleanup script to remove old Greek audio lessons that were generated
before Azure TTS integration (which only had female voices).

This script:
1. Finds all Greek audio lessons in the database
2. Deletes the database records
3. Deletes the audio files from disk
4. Clears cached audio segments for Greek

Run this to force regeneration of Greek lessons with proper male/female voices.

Usage:
    python -m tools.cleanup_greek_audio_lessons [--dry-run]

Options:
    --dry-run: Show what would be deleted without actually deleting
"""

import os
import sys
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.core.model import db
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning
from zeeguu.core.model.language import Language
from zeeguu.config import ZEEGUU_DATA_FOLDER


def cleanup_greek_audio_lessons(dry_run=False):
    """
    Remove all Greek audio lessons from database and filesystem.

    Args:
        dry_run: If True, only report what would be deleted without actually deleting
    """

    print("=" * 70)
    print("Greek Audio Lessons Cleanup Script")
    print("=" * 70)

    if dry_run:
        print("🔍 DRY RUN MODE - No actual changes will be made\n")
    else:
        print("⚠️  LIVE MODE - This will delete data!\n")

    # Get Greek language
    greek = Language.find_or_create("el")
    print(f"✓ Found Greek language: {greek} (id: {greek.id})\n")

    # Find all daily audio lessons for Greek
    daily_lessons = DailyAudioLesson.query.filter_by(language_id=greek.id).all()
    print(f"📊 Found {len(daily_lessons)} daily Greek audio lessons")

    # Find all individual meaning lessons for Greek words
    # (These are linked via meanings which have a language)
    meaning_lessons = (
        db.session.query(AudioLessonMeaning)
        .join(AudioLessonMeaning.meaning)
        .filter_by(language_id=greek.id)
        .all()
    )
    print(f"📊 Found {len(meaning_lessons)} individual Greek meaning lessons\n")

    # Audio file paths to delete
    audio_files_to_delete = []

    # Process daily lessons
    print("-" * 70)
    print("DAILY LESSONS:")
    print("-" * 70)

    for lesson in daily_lessons:
        print(f"  • Daily lesson {lesson.id} for user {lesson.user_id}")
        print(f"    Created: {lesson.created_at}")
        print(f"    Completed: {'Yes' if lesson.is_completed else 'No'}")

        # Get audio file path
        audio_file = os.path.join(
            ZEEGUU_DATA_FOLDER,
            "audio/daily_lessons",
            f"{lesson.id}.mp3"
        )
        if os.path.exists(audio_file):
            audio_files_to_delete.append(audio_file)
            print(f"    Audio file: {audio_file} (exists)")
        else:
            print(f"    Audio file: {audio_file} (not found)")
        print()

    # Process meaning lessons
    print("-" * 70)
    print("MEANING LESSONS:")
    print("-" * 70)

    for lesson in meaning_lessons:
        print(f"  • Meaning lesson {lesson.id}")
        print(f"    Word: {lesson.meaning.from_lang_word}")
        print(f"    Translation: {lesson.meaning.to_lang_word}")
        print(f"    CEFR: {lesson.difficulty_level}")

        # Get audio file path
        audio_file = os.path.join(
            ZEEGUU_DATA_FOLDER,
            "audio/lessons",
            f"{lesson.id}.mp3"
        )
        if os.path.exists(audio_file):
            audio_files_to_delete.append(audio_file)
            print(f"    Audio file: {audio_file} (exists)")
        else:
            print(f"    Audio file: {audio_file} (not found)")
        print()

    # Find cached Greek audio segments
    segments_dir = os.path.join(ZEEGUU_DATA_FOLDER, "audio/segments")
    greek_segments = []

    if os.path.exists(segments_dir):
        for filename in os.listdir(segments_dir):
            if filename.startswith("el-GR-") or filename.startswith("ro-RO-"):
                greek_segments.append(os.path.join(segments_dir, filename))

    print("-" * 70)
    print("CACHED SEGMENTS:")
    print("-" * 70)
    print(f"📊 Found {len(greek_segments)} cached Greek/Romanian segments")
    for segment in greek_segments[:10]:  # Show first 10
        print(f"  • {os.path.basename(segment)}")
    if len(greek_segments) > 10:
        print(f"  ... and {len(greek_segments) - 10} more")
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY:")
    print("=" * 70)
    print(f"Daily lessons to delete:    {len(daily_lessons)}")
    print(f"Meaning lessons to delete:  {len(meaning_lessons)}")
    print(f"Audio files to delete:      {len(audio_files_to_delete)}")
    print(f"Cached segments to delete:  {len(greek_segments)}")
    print("=" * 70)
    print()

    if dry_run:
        print("✓ Dry run complete - no changes made")
        return

    # Confirm deletion
    response = input("⚠️  Are you sure you want to DELETE all of this? (yes/no): ")
    if response.lower() != "yes":
        print("❌ Aborted - no changes made")
        return

    print("\n🗑️  Deleting data...\n")

    # Delete from database (cascading will handle segments)
    deleted_count = 0

    print("Deleting daily lessons from database...")
    for lesson in daily_lessons:
        db.session.delete(lesson)
        deleted_count += 1
    print(f"  ✓ Marked {deleted_count} daily lessons for deletion")

    deleted_count = 0
    print("Deleting meaning lessons from database...")
    for lesson in meaning_lessons:
        db.session.delete(lesson)
        deleted_count += 1
    print(f"  ✓ Marked {deleted_count} meaning lessons for deletion")

    # Commit database changes
    print("Committing database changes...")
    db.session.commit()
    print("  ✓ Database changes committed")

    # Delete audio files
    deleted_files = 0
    print("\nDeleting audio files...")
    for audio_file in audio_files_to_delete:
        try:
            os.remove(audio_file)
            deleted_files += 1
        except OSError as e:
            print(f"  ⚠️  Failed to delete {audio_file}: {e}")
    print(f"  ✓ Deleted {deleted_files} audio files")

    # Delete cached segments
    deleted_segments = 0
    print("\nDeleting cached segments...")
    for segment in greek_segments:
        try:
            os.remove(segment)
            deleted_segments += 1
        except OSError as e:
            print(f"  ⚠️  Failed to delete {segment}: {e}")
    print(f"  ✓ Deleted {deleted_segments} cached segments")

    print("\n" + "=" * 70)
    print("✅ CLEANUP COMPLETE")
    print("=" * 70)
    print("\nNew Greek audio lessons will be regenerated with:")
    print("  • Azure TTS (both male and female voices)")
    print("  • Improved script generation")
    print("  • Updated voice configuration")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup old Greek audio lessons to force regeneration with Azure TTS"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )

    args = parser.parse_args()

    try:
        cleanup_greek_audio_lessons(dry_run=args.dry_run)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
