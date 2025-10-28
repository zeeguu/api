#!/usr/bin/env python
"""
Cleanup script to remove old Greek audio files that were generated
before Azure TTS integration (which only had female voices).

This script:
1. Finds all Greek audio lessons in the database
2. Analyzes scripts to see which have both Man/Woman speakers
3. Deletes ONLY the audio files (keeps database records with scripts)
4. Clears cached audio segments for Greek

The system will regenerate audio when lessons are requested again.

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
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.phrase import Phrase
from zeeguu.config import ZEEGUU_DATA_FOLDER


def analyze_script(script):
    """Check if script has both Man and Woman speakers."""
    has_man = "Man:" in script
    has_woman = "Woman:" in script
    return has_man, has_woman


def cleanup_greek_audio_lessons(dry_run=False):
    """
    Remove Greek audio files (keeps database records).

    Args:
        dry_run: If True, only report what would be deleted without actually deleting
    """

    print("=" * 70)
    print("Greek Audio Lessons Cleanup Script")
    print("=" * 70)

    if dry_run:
        print("🔍 DRY RUN MODE - No actual changes will be made")
    else:
        print("⚠️  LIVE MODE - This will delete audio files!")

    print("✓ Database records will be kept, only audio files deleted")
    print()

    # Get Greek language
    greek = Language.find_or_create("el")
    print(f"✓ Found Greek language: {greek} (id: {greek.id})\n")

    # Find all daily audio lessons for Greek
    daily_lessons = DailyAudioLesson.query.filter_by(language_id=greek.id).all()
    print(f"📊 Found {len(daily_lessons)} daily Greek audio lessons")

    # Find all individual meaning lessons for Greek words
    # (Join through meaning -> origin phrase -> language)
    meaning_lessons = (
        db.session.query(AudioLessonMeaning)
        .join(Meaning, AudioLessonMeaning.meaning_id == Meaning.id)
        .join(Phrase, Meaning.origin_id == Phrase.id)
        .filter(Phrase.language_id == greek.id)
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

    # Process meaning lessons and analyze scripts
    print("-" * 70)
    print("MEANING LESSONS:")
    print("-" * 70)

    scripts_with_both = 0
    scripts_woman_only = 0
    scripts_man_only = 0
    scripts_neither = 0

    for lesson in meaning_lessons:
        has_man, has_woman = analyze_script(lesson.script)

        # Track statistics
        if has_man and has_woman:
            scripts_with_both += 1
            status = "✓ Both speakers"
        elif has_woman and not has_man:
            scripts_woman_only += 1
            status = "⚠️  Woman only"
        elif has_man and not has_woman:
            scripts_man_only += 1
            status = "⚠️  Man only"
        else:
            scripts_neither += 1
            status = "❌ Neither speaker"

        print(f"  • Meaning lesson {lesson.id} - {status}")
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

        # Print script content
        print(f"    Script preview:")
        script_lines = lesson.script.split('\n')
        for i, line in enumerate(script_lines[:8]):  # Show first 8 lines
            if line.strip():
                print(f"      {line[:80]}")  # Truncate long lines
        if len(script_lines) > 8:
            print(f"      ... ({len(script_lines) - 8} more lines)")
        print()

    print("-" * 70)
    print("SCRIPT ANALYSIS:")
    print("-" * 70)
    print(f"✓ Scripts with both Man & Woman: {scripts_with_both}")
    print(f"⚠️  Scripts with Woman only:       {scripts_woman_only}")
    print(f"⚠️  Scripts with Man only:          {scripts_man_only}")
    print(f"❌ Scripts with neither:          {scripts_neither}")
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
    print(f"Daily lessons (keep in DB): {len(daily_lessons)}")
    print(f"Meaning lessons (keep in DB): {len(meaning_lessons)}")
    print(f"Audio files to delete:      {len(audio_files_to_delete)}")
    print(f"Cached segments to delete:  {len(greek_segments)}")
    print("=" * 70)
    print()

    if dry_run:
        print("✓ Dry run complete - no changes made")
        return

    # Confirm deletion
    response = input("⚠️  Are you sure you want to DELETE audio files? (yes/no): ")

    if response.lower() != "yes":
        print("❌ Aborted - no changes made")
        return

    print("\n🗑️  Deleting audio files...\n")
    print("✓ Keeping database records (only deleting audio files)")
    print("  Audio will be regenerated with new Azure voices when lessons are requested")

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
    print("\nAudio files have been deleted. Database records kept.")
    print("When users request lessons, audio will be regenerated with:")
    print("  • Azure TTS (both male and female voices)")
    print("  • Improved script generation (requires both speakers)")
    print("  • Updated voice configuration")
    print("\n💡 NOTE: Audio is regenerated automatically when users request lessons")
    print("   No manual intervention needed!")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup old Greek audio files to force regeneration with Azure TTS"
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
