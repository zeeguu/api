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
    python -m tools.audit_audio_lesson_script_languages --deprecate --force  # ...more than 10
    python -m tools.audit_audio_lesson_script_languages --quiet         # print only if something is wrong

--quiet is for the nightly cron: a clean run prints nothing at all, so cron stays
silent and any output is a real finding. This is the safety net under the
generation-time check, which is a tuned heuristic and has been wrong in both
directions; a script it wrongly passes leaves no log line anywhere, and sweeping
what is already stored is the only thing that finds it.

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

from zeeguu.core.audio_lessons.script_generator import _is_a_script
from zeeguu.core.audio_lessons.script_language_validator import find_language_mismatches
from zeeguu.core.language.language_check import describe_mismatches
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning

DEPRECATE = "--deprecate" in sys.argv
FORCE = "--force" in sys.argv

# Deprecating is reversible only while you still know which rows moved. On
# 2026-08-18 a --deprecate run acted on a report from a configuration that was one
# commit old and stamped sixty lessons, fifty-six of them sound; they were
# recoverable only because one run shares one timestamp and almost nothing had
# regenerated yet. A sweep that finds this many at once has found a change in the
# checker, not a change in the corpus.
MAX_WITHOUT_FORCE = 10
QUIET = "--quiet" in sys.argv
LANGUAGE = None
if "--language" in sys.argv:
    LANGUAGE = sys.argv[sys.argv.index("--language") + 1]

_buffered = []


def out(line=""):
    """Under --quiet, hold everything back until we know there is a finding."""
    if QUIET:
        _buffered.append(line)
    else:
        print(line)


def flush():
    for line in _buffered:
        print(line)
    _buffered.clear()


out(f"Mode: {'DEPRECATE bad scripts' if DEPRECATE else 'REPORT ONLY'}")
if LANGUAGE:
    out(f"Learned language filter: {LANGUAGE}")
out()


def teacher_code(lesson):
    return lesson.teacher_language.code if lesson.teacher_language else "en"


def audit(label, lessons, learned_code_of, describe):
    """Check each lesson's script and return the ones whose language is wrong."""
    out("=" * 70)
    out(f"{label}: {len(lessons)} to check")
    out("=" * 70)

    bad = []
    not_scripts = []
    for lesson in lessons:
        learned = learned_code_of(lesson)
        if LANGUAGE and learned != LANGUAGE:
            continue

        if not _is_a_script(lesson.script):
            # Not a wrong-language script — not a script. The model answered with a
            # refusal or a correction of the request and it was stored as a lesson.
            # Reported separately because "too little text to judge" hid these.
            not_scripts.append(lesson)
            out(f"  [{lesson.id}] {describe(lesson)} ({learned}) — NOT A SCRIPT: "
                f"{lesson.script.strip()[:90]!r}")
            continue
        mismatches = find_language_mismatches(
            lesson.script,
            target_language=learned,
            source_language=teacher_code(lesson),
            label_for_log=f"[{lesson.id}] {describe(lesson)[:40]}",
        )
        if mismatches:
            bad.append(lesson)
            out(f"  [{lesson.id}] {describe(lesson)} ({learned}/{teacher_code(lesson)})")
            out(f"      {describe_mismatches(mismatches)}")

    out(f"  → {len(bad)} with a wrong-language script")
    if not_scripts:
        out(f"  → {len(not_scripts)} that are not scripts at all")
    out()
    return bad + not_scripts


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
    condemned = bad_meanings + bad_dialogues

    # Say exactly what is about to move, so the run is auditable afterwards from
    # the log alone.
    out("About to deprecate:")
    for lesson in condemned:
        out(f"    {type(lesson).__name__} {lesson.id}")

    if len(condemned) > MAX_WITHOUT_FORCE and not FORCE:
        out(
            f"\nREFUSING: {len(condemned)} lessons is more than {MAX_WITHOUT_FORCE}. "
            "That usually means the checker changed, not the corpus. Read the list, "
            "then re-run with --force if it is really right."
        )
        flush()
        sys.exit(1)

    now = datetime.now()
    for lesson in condemned:
        lesson.deprecated_at = now
    db.session.commit()
    out(
        f"Deprecated {len(bad_meanings)} meaning lessons and "
        f"{len(bad_dialogues)} dialogues. They will be regenerated on next request."
    )
elif bad_meanings or bad_dialogues:
    out("Run again with --deprecate to mark these for regeneration.")
else:
    out("No wrong-language scripts found.")

if QUIET and (bad_meanings or bad_dialogues):
    flush()
