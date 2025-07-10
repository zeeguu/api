#!/usr/bin/env python3
"""
Script to delete all Portuguese audio lessons from the database.
This is needed because they were generated with Brazilian Portuguese voices
instead of European Portuguese voices.
"""
import os
import sys

# Add the parent directory to Python path to import zeeguu modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.core.model import db
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.language import Language
from zeeguu.api.app import create_app


def delete_portuguese_audio_lessons():
    """Delete all audio lessons for Portuguese language."""
    app = create_app()

    with app.app_context():
        # Find Portuguese language
        portuguese = Language.find("pt")
        if not portuguese:
            print("Portuguese language not found in database!")
            return

        print(
            f"Found Portuguese language: {portuguese.name} (code: {portuguese.code}, id: {portuguese.id})"
        )

        # Count Portuguese lessons before deletion
        portuguese_lessons = DailyAudioLesson.query.filter_by(
            language_id=portuguese.id
        ).all()
        total_count = len(portuguese_lessons)

        if total_count == 0:
            print("No Portuguese audio lessons found.")
            return

        print(f"\nFound {total_count} Portuguese audio lessons to delete.")
        print("\nLesson details:")
        print("-" * 80)

        for lesson in portuguese_lessons:
            print(f"Lesson ID: {lesson.id}")
            print(f"  User: {lesson.user.name} (ID: {lesson.user_id})")
            print(f"  Created: {lesson.created_at}")
            print(f"  Segments: {len(lesson.segments)}")
            print(f"  Duration: {lesson.duration_seconds}s")
            print(f"  Completed: {'Yes' if lesson.is_completed else 'No'}")
            print(f"  Audio file: {lesson.audio_file_path}")
            print()

        # Ask for confirmation
        print("-" * 80)
        confirmation = input(
            f"\nAre you sure you want to delete all {total_count} Portuguese audio lessons? (yes/no): "
        )

        if confirmation.lower() != "yes":
            print("Deletion cancelled.")
            return

        # Delete the lessons
        deleted_count = 0
        for lesson in portuguese_lessons:
            # Delete the audio file if it exists
            audio_path = f"/audio/daily_lessons/{lesson.id}.mp3"
            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    print(f"Deleted audio file: {audio_path}")
                except Exception as e:
                    print(f"Warning: Could not delete audio file {audio_path}: {e}")

            # Delete from database (cascade will handle segments)
            db.session.delete(lesson)
            deleted_count += 1

        # Commit the changes
        db.session.commit()

        print(
            f"\n✓ Successfully deleted {deleted_count} Portuguese audio lessons from database."
        )
        print("Note: The associated segments were also deleted due to cascade delete.")


if __name__ == "__main__":
    delete_portuguese_audio_lessons()
