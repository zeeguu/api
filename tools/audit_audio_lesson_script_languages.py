#!/usr/bin/env python
"""
Find audio lesson scripts that were generated in the wrong language.

Scripts are cached and reused — an AudioLessonMeaning is reused for everyone
learning that meaning, and a general AudioLessonDialogue is reused across users —
so one script the LLM wrote in the wrong language keeps being served until it is
deprecated. New scripts are checked at generation time by
zeeguu.core.audio_lessons.script_language_validator; this tool covers the ones
already in the database.

Usage:
    python -m tools.audit_audio_lesson_script_languages                 # report only
    python -m tools.audit_audio_lesson_script_languages --language da   # one learned language
    python -m tools.audit_audio_lesson_script_languages --deprecate     # mark the bad ones

--deprecate sets deprecated_at, so cache lookups regenerate while daily lessons
that already reference the row keep playing.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.audio_lessons.script_language_validator import find_language_mismatches
from zeeguu.core.language.language_check import describe_mismatches
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning

DEPRECATE = "--deprecate" in sys.argv
LANGUAGE = None
if "--language" in sys.argv:
    LANGUAGE = sys.argv[sys.argv.index("--language") + 1]

print(f"Mode: {'DEPRECATE bad scripts' if DEPRECATE else 'REPORT ONLY'}")
if LANGUAGE:
    print(f"Learned language filter: {LANGUAGE}")
print()


def teacher_code(lesson):
    return lesson.teacher_language.code if lesson.teacher_language else "en"


def audit(label, lessons, learned_code_of, describe):
    """Check each lesson's script and return the ones whose language is wrong."""
    print("=" * 70)
    print(f"{label}: {len(lessons)} to check")
    print("=" * 70)

    bad = []
    for lesson in lessons:
        learned = learned_code_of(lesson)
        if LANGUAGE and learned != LANGUAGE:
            continue
        mismatches = find_language_mismatches(
            lesson.script, target_language=learned, source_language=teacher_code(lesson)
        )
        if mismatches:
            bad.append(lesson)
            print(f"  [{lesson.id}] {describe(lesson)} ({learned}/{teacher_code(lesson)})")
            print(f"      {describe_mismatches(mismatches)}")

    print(f"  → {len(bad)} with a wrong-language script")
    print()
    return bad


meanings = AudioLessonMeaning.query.filter(
    AudioLessonMeaning.deprecated_at.is_(None)
).all()
bad_meanings = audit(
    "AudioLessonMeaning",
    meanings,
    learned_code_of=lambda m: m.meaning.origin.language.code,
    describe=lambda m: f"{m.meaning.origin.content} → {m.meaning.translation.content}",
)

dialogues = AudioLessonDialogue.query.filter(
    AudioLessonDialogue.deprecated_at.is_(None)
).all()
bad_dialogues = audit(
    "AudioLessonDialogue",
    dialogues,
    learned_code_of=lambda d: d.language.code,
    describe=lambda d: d.title or d.canonical_suggestion,
)

if DEPRECATE and (bad_meanings or bad_dialogues):
    now = datetime.now()
    for lesson in bad_meanings + bad_dialogues:
        lesson.deprecated_at = now
    db.session.commit()
    print(
        f"Deprecated {len(bad_meanings)} meaning lessons and "
        f"{len(bad_dialogues)} dialogues. They will be regenerated on next request."
    )
elif bad_meanings or bad_dialogues:
    print("Run again with --deprecate to mark these for regeneration.")
else:
    print("No wrong-language scripts found.")
