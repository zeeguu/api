#!/usr/bin/env python3
"""
Delete today's daily audio lessons for a given user.

Usage:
    python -m tools.delete_daily_lesson <user_id> [language_code]

Without language_code: deletes today's lessons in ALL languages.
With language_code (e.g. 'it', 'da'): deletes only that language's lesson.
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db, User
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.language import Language
from zeeguu.config import ZEEGUU_DATA_FOLDER


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m tools.delete_daily_lesson <user_id> [language_code]")
        sys.exit(1)

    user_id = int(sys.argv[1])
    lang_filter = sys.argv[2] if len(sys.argv) > 2 else None

    app = create_app()
    with app.app_context():
        user = User.find_by_id(user_id)
        if not user:
            print(f"User {user_id} not found.")
            sys.exit(1)

        print(f"User: {user.name} (ID: {user.id})")

        # Find today's lessons (generous window: last 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        query = DailyAudioLesson.query.filter_by(user_id=user.id).filter(
            DailyAudioLesson.created_at >= cutoff
        )

        if lang_filter:
            language = Language.find(lang_filter)
            if not language:
                print(f"Language '{lang_filter}' not found.")
                sys.exit(1)
            query = query.filter_by(language_id=language.id)

        lessons = query.all()

        if not lessons:
            print("No recent lessons found.")
            return

        for lesson in lessons:
            lang_name = lesson.language.name if lesson.language else "?"
            print(f"  Deleting lesson {lesson.id} ({lang_name}, created {lesson.created_at})")

            # Delete audio file
            audio_path = os.path.join(
                ZEEGUU_DATA_FOLDER, "audio", "daily_lessons", f"{lesson.id}.mp3"
            )
            if os.path.exists(audio_path):
                os.remove(audio_path)
                print(f"    Deleted audio file")

            db.session.delete(lesson)

        db.session.commit()
        print(f"\nDeleted {len(lessons)} lesson(s).")


if __name__ == "__main__":
    main()
