#!/usr/bin/env python
"""
Find meaning lessons that teach their word wrong.

An AudioLessonMeaning is reused for everyone learning that meaning, so one wrong
script keeps being served until it is deprecated. At build time nothing checks
what the lines mean: only their language (script_language_validator) and that
the model wrote a script at all (NotAScript). On 2026-10-18 lesson 41749 taught
Danish "Sådan" as "How" and had learners say "Sådan gør du det?" for "How do you
do it?"; the pair was right in the headline it came from, the lesson was not.
On the same day 352 live lessons sat on meanings our own translation validator
marks invalid, because the audio word selector never looks at meaning.validated.

Each lesson is read by DeepSeek against its word, its translation and the
sentence the word was looked up in (zeeguu.core.audio_lessons.
lesson_correctness_check). Pairs the translation validator never passed
(meaning.validated 0 or 2) are also judged again in that sentence.

Usage:
    python -m tools.audit_meaning_lesson_correctness                  # report only
    python -m tools.audit_meaning_lesson_correctness --language da    # one learned language
    python -m tools.audit_meaning_lesson_correctness --ids 41749,123  # just these lessons
    python -m tools.audit_meaning_lesson_correctness --sample 200     # a random sample
    python -m tools.audit_meaning_lesson_correctness --deprecate      # mark the failed ones
    python -m tools.audit_meaning_lesson_correctness --deprecate --force  # ...more than 10
    python -m tools.audit_meaning_lesson_correctness --quiet          # print only new fails

The report is JSON lines in --report (default
$ZEEGUU_DATA_FOLDER/meaning_lesson_audit/report.jsonl), one row per lesson:
id, language, word, translation, validated, context, pair verdict, verdict,
problems. A run skips lessons that already have a verdict from the same checker
(model and prompt text), so an interrupted run resumes and a nightly run checks
only the new lessons. Calls are spread over --workers threads, at most one
starting every --interval seconds.

--deprecate sets deprecated_at on the lessons the report fails for a blocking
problem (any kind but "unnatural", as at build time), and marks INVALID the
meanings whose pair the pair-only verdict confirmed wrong (each learner's word
on them is then judged in its own sentence by the nightly
validate_scheduled_meanings), so cache lookups
regenerate while daily lessons that already reference the row keep playing.
"""

import argparse
import os
import random
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.audio_lessons.lesson_correctness_check import (
    ABOUT_THE_DATA,
    FAIL,
    LessonToCheck,
    blocking,
    check_all,
    checker_id,
    is_done,
    mark_pair_invalid,
    read_report,
)
from zeeguu.core.audio_lessons.daily_lesson_generator import _lookup_sentence
from zeeguu.core.audio_lessons.script_generator import _is_a_script
from zeeguu.core.llm_services.validation_service import changes_the_word
from zeeguu.core.llm_services.deepseek_service import DeepSeekService
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning
from zeeguu.core.model.language import Language
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.phrase import Phrase
from zeeguu.core.model.user_word import UserWord

# Deprecating is reversible only while you still know which rows moved. On
# 2026-08-18 a --deprecate run of the language audit acted on a report from a
# configuration that was one commit old and stamped sixty lessons, fifty-six of
# them sound. Here the report outlives the run, so --deprecate trusts only rows
# whose checker id (model and a hash of the prompt text) is the current one: a
# changed prompt makes every earlier verdict stale instead of actionable.
MAX_WITHOUT_FORCE = 10

parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
parser.add_argument("--language", help="only lessons for this learned language code")
parser.add_argument("--ids", help="comma-separated audio_lesson_meaning ids")
parser.add_argument("--sample", type=int, help="check a random sample of this size")
parser.add_argument("--seed", type=int, default=0, help="for --sample")
parser.add_argument("--report", help="JSON lines report to append to and resume from")
parser.add_argument("--workers", type=int, default=4)
parser.add_argument("--interval", type=float, default=0.5, help="seconds between request starts")
parser.add_argument("--deprecate", action="store_true")
parser.add_argument("--force", action="store_true")
parser.add_argument("--quiet", action="store_true", help="print nothing unless a lesson newly fails")
args = parser.parse_args()

REPORT = args.report or os.path.join(
    os.environ.get("ZEEGUU_DATA_FOLDER") or ".", "meaning_lesson_audit", "report.jsonl"
)
os.makedirs(os.path.dirname(os.path.abspath(REPORT)), exist_ok=True)

_buffered = []


def out(line=""):
    """Under --quiet, hold everything back until we know there is a finding."""
    if args.quiet:
        _buffered.append(line)
    else:
        print(line, flush=True)


def flush():
    for line in _buffered:
        print(line)
    _buffered.clear()


def learned_code(lesson):
    return lesson.meaning.origin.language.code


def context_of(meaning):
    """The sentence the word was first looked up in. A lesson is generated for
    the first learner who needs it, so the earliest user_word is the likeliest
    source of the translation the lesson was built on."""
    user_word = (
        UserWord.query.filter(UserWord.meaning_id == meaning.id)
        .filter(UserWord.preferred_bookmark_id.isnot(None))
        .order_by(UserWord.id)
        .first()
    )
    return _lookup_sentence(user_word) if user_word else None


def to_check(lesson):
    meaning = lesson.meaning
    return LessonToCheck(
        id=lesson.id,
        learned_language=learned_code(lesson),
        teacher_language=lesson.teacher_language.code if lesson.teacher_language else "en",
        translation_language=meaning.translation.language.code,
        word=meaning.origin.content,
        translation=meaning.translation.content,
        validated=meaning.validated,
        context=context_of(meaning),
        script=lesson.script,
    )


def describe(row):
    head = f"  [{row['id']}] {row['word']} → {row['translation']} ({row['language']}, validated={row['validated']})"
    lines = [head]
    if row.get("pair_verdict") == "FIX":
        lines.append(f"      pair: FIX {row.get('pair_correction', '')} — {row.get('pair_reason')}")
    for problem in row["problems"]:
        where = f"line {problem['line']}: {problem['text']!r} — " if problem.get("text") else ""
        lines.append(f"      [{problem.get('kind', 'other')}] {where}{problem['issue']}")
    return "\n".join(lines)


service = DeepSeekService()
CHECKER = checker_id(service.model)
report = read_report(REPORT)

query = AudioLessonMeaning.query.filter(AudioLessonMeaning.deprecated_at.is_(None))
if args.ids:
    query = query.filter(AudioLessonMeaning.id.in_([int(i) for i in args.ids.split(",")]))
if args.language:
    query = (
        query.join(Meaning, AudioLessonMeaning.meaning_id == Meaning.id)
        .join(Phrase, Meaning.origin_id == Phrase.id)
        .filter(Phrase.language_id == Language.find(args.language).id)
    )
lessons = query.all()
if args.sample:
    lessons = random.Random(args.seed).sample(lessons, min(args.sample, len(lessons)))

# Prose stored as a script is the language audit's finding (NOT A SCRIPT); there
# are no lines here to judge.
pending = [l for l in lessons if not is_done(report.get(l.id), CHECKER) and _is_a_script(l.script)]

out(f"Mode: {'DEPRECATE failed lessons' if args.deprecate else 'REPORT ONLY'}")
out(f"Checker: {CHECKER}")
out(f"Report: {REPORT}")
if args.language:
    out(f"Learned language filter: {args.language}")
out(f"{len(lessons)} live lessons selected, {len(pending)} to check")
out()

new_fails = []
errors = []


def on_row(row):
    report[row["id"]] = row
    # Only what would block it at build time: an "unnatural" line alone is
    # not a finding, and under --quiet it would mail every night
    if row["verdict"] == FAIL and blocking(row["problems"]):
        new_fails.append(row)
        out(describe(row))
    elif row["verdict"] not in ("pass", FAIL):
        errors.append(row)


check_all(
    service,
    (to_check(l) for l in pending),
    REPORT,
    workers=args.workers,
    interval=args.interval,
    on_row=on_row,
)

out()
out(f"→ {len(pending) - len(errors)} checked, {len(new_fails)} failed, {len(errors)} errors (retried next run)")

if args.deprecate:
    selected = {l.id: l for l in lessons}
    condemned_rows = [
        row
        for row in report.values()
        if row["id"] in selected
        and row["verdict"] == FAIL
        and row.get("checker") == CHECKER
        # The same rule as at build time (script_generator): "unnatural" alone
        # does not take a lesson away.
        and blocking(row["problems"])
    ]
    condemned = [selected[row["id"]] for row in condemned_rows]
    # As at build time (daily_lesson_generator): when the pair itself is wrong,
    # the meaning is marked INVALID too, or the selector would pick it again and
    # the next lesson would be built on the same pair.
    # Only pairs the pair-only verdict confirmed wrong, once per meaning: two
    # lessons (another teacher language or variety) can share one.
    wrong_pairs = list(
        {
            selected[row["id"]].meaning_id: row
            for row in condemned_rows
            # Both, as at build time: the lesson check said the pair is wrong
            # and the pair-only verdict confirmed it
            if row.get("pair_verdict") == "FIX"
            and any(p["kind"] in ABOUT_THE_DATA for p in row["problems"])
            # Not when the fix changes the word: then it was one learner's
            # selection that was wrong, not the pair (as in the validator)
            and not changes_the_word(row["word"], row.get("pair_corrected_word"))
        }.items()
    )

    # Say exactly what is about to move, so the run is auditable afterwards from
    # the log alone.
    out("About to deprecate:")
    for row in condemned_rows:
        kinds = ",".join(sorted({p["kind"] for p in blocking(row["problems"])}))
        out(f"    AudioLessonMeaning {row['id']} ({kinds})")
    out(
        f"...and mark INVALID the {len(wrong_pairs)} meanings whose word or "
        "translation is wrong"
    )

    if len(condemned) > MAX_WITHOUT_FORCE and not args.force:
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
    for meaning_id, row in wrong_pairs:
        why = [{"kind": "translation", "issue": row.get("pair_reason") or "pair judged wrong"}]
        mark_pair_invalid(db.session, meaning_id, why, context=row["context"])
    db.session.commit()
    out(
        f"Deprecated {len(condemned)} meaning lessons; they will be regenerated on next "
        f"request. Marked {len(wrong_pairs)} meanings INVALID."
    )
elif new_fails:
    out("Run again with --deprecate to mark the failed lessons for regeneration.")

# A deprecating run always prints: it may act on rows from an earlier run
# even when this one found nothing new.
if args.quiet and (new_fails or args.deprecate):
    flush()
