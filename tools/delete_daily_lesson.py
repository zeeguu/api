#!/usr/bin/env python3
"""
Delete today's daily audio lesson for a given user.

Usage:
    python -m tools.delete_daily_lesson <user_id>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db, User
from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m tools.delete_daily_lesson <user_id>")
        sys.exit(1)

    user_id = int(sys.argv[1])

    app = create_app()
    with app.app_context():
        user = User.find_by_id(user_id)
        if not user:
            print(f"User {user_id} not found.")
            sys.exit(1)

        print(f"User: {user.name} (ID: {user.id})")

        generator = DailyLessonGenerator()
        result = generator.delete_todays_lesson_for_user(user)
        print(result.get("message", result.get("error", result)))


if __name__ == "__main__":
    main()
