#!/usr/bin/env python
"""
Fix audio lessons that don't have teacher_language_id set.

All existing lessons were created with English teacher voice, so we set
their teacher_language_id to English. This preserves them for English
native speakers while new lessons will be generated for other native languages.

Usage:
    python -m tools.fix_audio_lesson_teacher_language [--dry-run]
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning
from zeeguu.core.model.language import Language

app = create_app()
app.app_context().push()

DRY_RUN = "--dry-run" in sys.argv

print(f"Mode: {'DRY RUN' if DRY_RUN else 'LIVE - WILL UPDATE'}")
print()

# Get English language
english = Language.find_or_create("en")
print(f"English language id: {english.id}")

# Find AudioLessonMeaning records without teacher_language_id set
lessons_without_teacher_lang = AudioLessonMeaning.query.filter(
    AudioLessonMeaning.teacher_language_id == None
).all()

print(f"Found {len(lessons_without_teacher_lang)} AudioLessonMeaning records without teacher_language_id")
print()

if not lessons_without_teacher_lang:
    print("Nothing to update.")
    sys.exit(0)

updated_count = 0
for lesson in lessons_without_teacher_lang:
    if DRY_RUN:
        print(f"  Would set teacher_language_id={english.id} for AudioLessonMeaning {lesson.id}")
    else:
        lesson.teacher_language_id = english.id
    updated_count += 1

if not DRY_RUN:
    db.session.commit()
    print(f"Updated {updated_count} records.")
    print("Changes committed to database.")
else:
    print()
    print(f"Would update {updated_count} records.")
    print("This was a dry run. Run without --dry-run to actually update.")
