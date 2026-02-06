#!/usr/bin/env python
"""
Fix audio lessons teacher_language after the native voice feature.

1. OLD lessons (before yesterday): Set teacher_language_id to English
   - These were generated correctly with English teacher voice

2. RECENT lessons (yesterday and today): Delete them
   - These have English scripts but wrong voice (e.g., Ukrainian voice reading English)
   - The MP3 files are also deleted

Usage:
    python -m tools.fix_audio_lesson_teacher_language [--dry-run]
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.language import Language
from zeeguu.config import ZEEGUU_DATA_FOLDER

app = create_app()
app.app_context().push()

DRY_RUN = "--dry-run" in sys.argv

print(f"Mode: {'DRY RUN' if DRY_RUN else 'LIVE - WILL UPDATE/DELETE'}")
print()

# Cutoff: lessons created before yesterday are old (and correct)
# Lessons from yesterday onwards are buggy
yesterday = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
print(f"Cutoff date: {yesterday}")
print(f"  - Lessons BEFORE this: set teacher_language to English")
print(f"  - Lessons ON/AFTER this: delete (buggy)")
print()

# Get English language
english = Language.find_or_create("en")
print(f"English language id: {english.id}")
print()

# Audio directories
audio_dir = ZEEGUU_DATA_FOLDER + "/audio"
lessons_dir = os.path.join(audio_dir, "lessons")
daily_lessons_dir = os.path.join(audio_dir, "daily_lessons")

# ============================================================
# PART 1: Set old lessons to English
# ============================================================
print("=" * 60)
print("PART 1: Setting old lessons to English")
print("=" * 60)

# We need to find lessons without teacher_language that were created before yesterday
# AudioLessonMeaning doesn't have created_at, so we'll use the DailyAudioLesson.created_at
# to determine which meanings are old vs new

# Get all meanings without teacher_language
all_without_teacher = AudioLessonMeaning.query.filter(
    AudioLessonMeaning.teacher_language_id == None
).all()

print(f"Found {len(all_without_teacher)} AudioLessonMeaning records without teacher_language_id")

# Find which ones are referenced by recent daily lessons
recent_meaning_ids = set()
recent_daily_lessons = DailyAudioLesson.query.filter(
    DailyAudioLesson.created_at >= yesterday
).all()

for daily_lesson in recent_daily_lessons:
    for segment in daily_lesson.segments:
        if segment.audio_lesson_meaning_id:
            recent_meaning_ids.add(segment.audio_lesson_meaning_id)

print(f"Found {len(recent_meaning_ids)} meanings used in recent (buggy) daily lessons")

# Old = without teacher_language AND not in recent
old_audio_meanings = [m for m in all_without_teacher if m.id not in recent_meaning_ids]
print(f"Old AudioLessonMeaning records to update: {len(old_audio_meanings)}")

updated_count = 0
renamed_files = 0
for audio_meaning in old_audio_meanings:
    # Set teacher_language to English
    if DRY_RUN:
        print(f"  Would set teacher_language_id={english.id} for AudioLessonMeaning {audio_meaning.id}")
    else:
        audio_meaning.teacher_language_id = english.id
    updated_count += 1

    # Rename MP3 file from {id}.mp3 to {meaning_id}-en.mp3
    old_path = os.path.join(lessons_dir, f"{audio_meaning.id}.mp3")
    new_path = os.path.join(lessons_dir, f"{audio_meaning.meaning_id}-en.mp3")

    if os.path.exists(old_path):
        if DRY_RUN:
            print(f"  Would rename: {old_path} -> {new_path}")
        else:
            os.rename(old_path, new_path)
            print(f"  Renamed: {audio_meaning.id}.mp3 -> {audio_meaning.meaning_id}-en.mp3")
        renamed_files += 1

if not DRY_RUN and updated_count > 0:
    db.session.flush()

print(f"{'Would update' if DRY_RUN else 'Updated'} {updated_count} old lessons to English")
print(f"{'Would rename' if DRY_RUN else 'Renamed'} {renamed_files} MP3 files")
print()

# ============================================================
# PART 2: Delete recent buggy lessons
# ============================================================
print("=" * 60)
print("PART 2: Deleting recent buggy lessons")
print("=" * 60)

# Recent meanings to delete
recent_meanings = [m for m in all_without_teacher if m.id in recent_meaning_ids]
print(f"Recent buggy DailyAudioLesson records to delete: {len(recent_daily_lessons)}")
print(f"Recent buggy AudioLessonMeaning records to delete: {len(recent_meanings)}")

deleted_meaning_files = 0
deleted_daily_files = 0
deleted_meanings = 0
deleted_daily_lessons = 0

# Delete DailyAudioLesson first (segments have FK to AudioLessonMeaning)
for daily_lesson in recent_daily_lessons:
    mp3_path = os.path.join(daily_lessons_dir, f"{daily_lesson.id}.mp3")

    if os.path.exists(mp3_path):
        if DRY_RUN:
            print(f"  Would delete file: {mp3_path}")
        else:
            os.remove(mp3_path)
            print(f"  Deleted file: {mp3_path}")
        deleted_daily_files += 1

    if not DRY_RUN:
        db.session.delete(daily_lesson)
    deleted_daily_lessons += 1

# Now safe to delete AudioLessonMeaning records (no more FK references)
for audio_meaning in recent_meanings:
    mp3_path = os.path.join(lessons_dir, f"{audio_meaning.id}.mp3")

    if os.path.exists(mp3_path):
        if DRY_RUN:
            print(f"  Would delete file: {mp3_path}")
        else:
            os.remove(mp3_path)
            print(f"  Deleted file: {mp3_path}")
        deleted_meaning_files += 1

    if not DRY_RUN:
        db.session.delete(audio_meaning)
    deleted_meanings += 1

if not DRY_RUN:
    db.session.commit()
    print()
    print("Changes committed to database.")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Old lessons {'would be ' if DRY_RUN else ''}set to English: {updated_count}")
print(f"Old MP3 files {'would be ' if DRY_RUN else ''}renamed to new format: {renamed_files}")
print(f"Recent AudioLessonMeaning records {'would be ' if DRY_RUN else ''}deleted: {deleted_meanings}")
print(f"Recent DailyAudioLesson records {'would be ' if DRY_RUN else ''}deleted: {deleted_daily_lessons}")
print(f"MP3 files (meanings) {'would be ' if DRY_RUN else ''}deleted: {deleted_meaning_files}")
print(f"MP3 files (daily) {'would be ' if DRY_RUN else ''}deleted: {deleted_daily_files}")

if DRY_RUN:
    print()
    print("This was a dry run. Run without --dry-run to actually make changes.")
