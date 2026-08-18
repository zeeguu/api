#!/usr/bin/env python
"""
One-off: dump the full script of every meaning lesson the language check flags.

The audit prints a 120-character sample, which is enough to see THAT something
was flagged and not enough to see WHY. On the 2026-08-18 run, 17 of 6532 meaning
lessons were flagged and only about three were genuinely in the wrong language;
the rest look like correct text the detector misread. Deciding which needs the
whole script — specifically whether the target-language lines are conversational
prose or short repeated drill phrases.

Prints, per flagged lesson: the languages, what the detector said, and the target
voice lines in script order, one per line, so the shape is visible.

Usage:
    python -m tools._dump_flagged_meaning_lesson_scripts
    python -m tools._dump_flagged_meaning_lesson_scripts --language it
"""

import sys

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.audio_lessons.script_parser import parse_script
from zeeguu.core.audio_lessons.script_language_validator import (
    TARGET_LANGUAGE_VOICES,
    find_language_mismatches,
)
from zeeguu.core.language.language_check import _chunk, describe_mismatches, language_mismatch
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning

LANGUAGE = None
if "--language" in sys.argv:
    LANGUAGE = sys.argv[sys.argv.index("--language") + 1]

lessons = AudioLessonMeaning.query.filter(
    AudioLessonMeaning.deprecated_at.is_(None)
).all()

flagged = 0
for lesson in lessons:
    learned = lesson.meaning.origin.language.code
    if LANGUAGE and learned != LANGUAGE:
        continue
    teacher = lesson.teacher_language.code if lesson.teacher_language else "en"
    mismatches = find_language_mismatches(lesson.script, target_language=learned)
    if not mismatches:
        continue

    flagged += 1
    target_lines = [
        text for voice, text, _ in parse_script(lesson.script)
        if voice in TARGET_LANGUAGE_VOICES
    ]
    chunks = _chunk(target_lines)

    print("=" * 78)
    print(f"[{lesson.id}] {lesson.meaning.origin.content} -> {lesson.meaning.translation.content}"
          f"   ({learned}/{teacher})")
    print(f"  {describe_mismatches(mismatches)}")
    print(f"  {len(target_lines)} target lines, {len(chunks)} chunk(s), "
          f"{sum(len(c) for c in chunks)} chars, "
          f"{len(set(l.strip().lower() for l in target_lines))} distinct")
    print("  --- chunk verdicts ---")
    for i, chunk in enumerate(chunks, 1):
        verdict = language_mismatch(chunk, learned)
        print(f"    {i}: {len(chunk):4d} chars  "
              f"{'reads as ' + verdict.detected if verdict else 'ok'}")
    print("  --- target voice lines, in order ---")
    for line in target_lines:
        print(f"    | {line}")
    print()

print(f"{flagged} flagged out of {len(lessons)} checked")
