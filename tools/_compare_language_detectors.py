#!/usr/bin/env python
"""
One-off: run langdetect and lingua over every stored audio lesson and compare.

The 21-lesson sample that motivated this is rigged in lingua's favour — fifteen
of them are exactly the lessons langdetect got wrong. What it cannot tell us is
whether lingua invents NEW false positives among the ~6500 lessons that currently
pass silently. This runs both over everything and prints the disagreements.

langdetect side: what ships today — dialogue lines only (drills truncated at the
first echo), chunked, flagged when >10% of the passage reads wrong.

lingua side: every line judged on its own against all Zeeguu languages, flagged
when more than LINE_SHARE of the judgeable lines miss. No chunking, no drill
truncation — per-line makes both unnecessary, which is the point.

lingua is not in requirements.txt yet. Inside the container:
    pip install lingua-language-detector

Usage:
    python -m tools._compare_language_detectors
    python -m tools._compare_language_detectors --limit 500
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
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning
from zeeguu.core.language.language_check import _CONFUSABLE_FAMILIES
from zeeguu.core.model.language import Language as ZLanguage

try:
    from lingua import IsoCode639_1, Language, LanguageDetectorBuilder
except ImportError:
    sys.exit("lingua is not installed. Inside the container: pip install lingua-language-detector")

LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0

# Flag a lesson when more than this share of its judgeable lines miss.
#
# The first run used 0.6 and got this backwards: it flagged fourteen sound Danish
# lessons at 61-91% while MISSING dialogues 235 and 236 at 44% and 33%. The cause
# was a strict got != want comparison per line, with none of the confusable-family
# tolerance the langdetect path has had all along, so every short Danish line
# reading as Norwegian counted as a miss. With families applied those lessons drop
# to 0-17% and the genuine ones stay at 100% (meaning lessons) or 33-44%
# (dialogues, whose Danish practice section dilutes their English conversation).
# Hence 0.3.
LINE_SHARE = 0.3
MIN_WORDS = 2  # the bare target word on its own line says nothing

# Zeeguu code -> lingua. 'no' is Bokmål there; Kurdish has no model, as in langdetect.
OVERRIDES = {"no": "NB", "zh-CN": "ZH"}


def lingua_language(code):
    iso_name = OVERRIDES.get(code, code.upper())
    iso = getattr(IsoCode639_1, iso_name, None)
    if iso is None:
        return None
    try:
        return Language.from_iso_code_639_1(iso)
    except Exception:
        return None


def accepted_codes(code):
    """The same tolerance the langdetect path uses: a family member is evidence."""
    for family in _CONFUSABLE_FAMILIES:
        if code in family:
            return set(family)
    return {code}


SUPPORTED = {c: lingua_language(c) for c in ZLanguage.LANGUAGE_NAMES}
CODE_OF = {l: c for c, l in SUPPORTED.items() if l}
CANDIDATES = sorted({l for l in SUPPORTED.values() if l}, key=lambda l: l.name)
print(f"lingua over {len(CANDIDATES)} of {len(SUPPORTED)} Zeeguu languages "
      f"(no model: {', '.join(c for c, l in SUPPORTED.items() if not l) or 'none'})")
DETECTOR = LanguageDetectorBuilder.from_languages(*CANDIDATES).build()


def target_lines(script):
    return [t for voice, t, _ in parse_script(script) if voice in TARGET_LANGUAGE_VOICES]


def lingua_verdict(lines, learned):
    want = SUPPORTED.get(learned)
    if want is None:
        return None, 0.0
    ok = accepted_codes(learned)
    judged = misses = 0
    worst = None
    for line in lines:
        if len(line.split()) < MIN_WORDS:
            continue
        judged += 1
        got = DETECTOR.detect_language_of(line)
        if CODE_OF.get(got) not in ok:
            misses += 1
            worst = worst or (line, got)
    if not judged:
        return None, 0.0
    share = misses / judged
    return (worst if share > LINE_SHARE else None), share


def run(label, lessons, learned_of, describe):
    print(f"\n{'='*78}\n{label}: {len(lessons)}\n{'='*78}")
    both = only_old = only_new = 0
    for lesson in lessons:
        learned = learned_of(lesson)
        lines = target_lines(lesson.script)
        old = bool(find_language_mismatches(lesson.script, target_language=learned))
        new, share = lingua_verdict(lines, learned)
        new = bool(new)
        if old and new:
            both += 1
        elif old:
            only_old += 1
            print(f"  [{lesson.id}] {describe(lesson)} ({learned}) — langdetect only, lingua {share:.0%}")
        elif new:
            only_new += 1
            print(f"  [{lesson.id}] {describe(lesson)} ({learned}) — LINGUA ONLY, {share:.0%} of lines miss")
            for line in lines[:6]:
                print(f"        | {line}")
    print(f"\n  both flagged: {both}   langdetect only: {only_old}   lingua only: {only_new}")
    return both, only_old, only_new


meanings = AudioLessonMeaning.query.filter(AudioLessonMeaning.deprecated_at.is_(None))
dialogues = AudioLessonDialogue.query.filter(AudioLessonDialogue.deprecated_at.is_(None))
if LIMIT:
    meanings, dialogues = meanings.limit(LIMIT), dialogues.limit(LIMIT)

run("AudioLessonMeaning", meanings.all(),
    lambda m: m.meaning.origin.language.code,
    lambda m: f"{m.meaning.origin.content} -> {m.meaning.translation.content}")
run("AudioLessonDialogue", dialogues.all(),
    lambda d: d.language.code,
    lambda d: (d.title or d.canonical_suggestion or "")[:50])
