#!/usr/bin/env python

"""
Pre-generate each opted-in user's DAILY audio lesson so it's waiting for them
when they open the app — no spinner, just press play.

A user "opts in" by configuring a daily lesson in the app, which creates a
DailyAudioSubscription(user, learned_language) holding the lesson type, subject,
on/off flag, and schedule (daily, or a weekday mask).

For each recently-active user with an ENABLED subscription for their currently
-learned language, we generate today's lesson unless: it isn't a scheduled day,
they already have one for their local "today", or generation is PAUSED because
the most recent lesson wasn't engaged with (DailyAudioLesson.waiting_paused_for,
from #643 — avoids piling up unheard lessons). Generation reuses the on-demand
pipeline (prepare_lesson_generation + generate_daily_lesson), synchronously.

Usage:
    python generate_daily_audio_lessons.py [--send-email] [--dry-run] [--days N] [--user-id ID]
"""

import argparse
from datetime import datetime, timezone, timedelta

parser = argparse.ArgumentParser(
    description="Pre-generate daily audio lessons for opted-in active users"
)
parser.add_argument("--send-email", action="store_true", help="Send summary email after completion")
parser.add_argument("--dry-run", action="store_true", help="Report what would happen without generating")
parser.add_argument("--days", type=int, default=30, help="Active-user window in days (default: 30)")
parser.add_argument("--user-id", type=int, default=None, help="Only process this user (for testing)")
args = parser.parse_args()

DAYS_SINCE_ACTIVE = args.days
DRY_RUN = args.dry_run

from zeeguu.api.app import create_app_for_scripts

app = create_app_for_scripts()
app.app_context().push()

import signal
import time
from collections import defaultdict

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

from zeeguu.core.model import (
    db,
    User,
    UserWord,
    DailyAudioLesson,
    DailyAudioSubscription,
    AudioLessonGenerationProgress,
)
from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator
from zeeguu.core.audio_lessons.script_generator import VALID_LESSON_TYPES
from zeeguu.core.audio_lessons.suggestion_validator import validate_suggestion
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

PER_USER_TIMEOUT_SECONDS = 600

generator = DailyLessonGenerator()


class OutputCapture:
    def __init__(self):
        self.output = []

    def write(self, text):
        print(text, end="")
        self.output.append(text)

    def get_output(self):
        return "".join(self.output)


output_capture = OutputCapture()


def output(text=""):
    output_capture.write(text + "\n")


class TimeoutException(Exception):
    pass


def user_timezone_offset_minutes(user):
    """Best-effort: the user's current UTC offset in minutes, derived from their
    stored timezone (e.g. "Europe/Copenhagen"). Defaults to 0/UTC when unknown,
    in which case far-west users may have "today" still be "yesterday" at run
    time — the frontend fallback covers that miss."""
    tz_name = getattr(user, "timezone", None)
    if not tz_name or ZoneInfo is None:
        return 0
    try:
        offset = datetime.now(ZoneInfo(tz_name)).utcoffset()
        return int(offset.total_seconds() // 60) if offset else 0
    except Exception:
        return 0


def resolve_suggestion(user, lesson_type, raw_suggestion):
    """Mirror the endpoint's canonicalization: reuse a cached canonical form if
    the user has had this exact subject before, otherwise validate it.

    Returns (canonical_suggestion, is_general) or raises ValueError if the
    subject is rejected by the validator."""
    if not raw_suggestion or lesson_type not in ("topic", "situation"):
        return None, False

    cached = DailyAudioLesson.find_canonical_for_raw_suggestion(user, raw_suggestion)
    if cached:
        return cached, False

    is_valid, result = validate_suggestion(raw_suggestion, lesson_type, user.native_language.name)
    if not is_valid:
        raise ValueError(result.get("reason", "rejected"))
    return result["canonical"], result["is_general"]


def decide_generation(user, language, timezone_offset, today_local):
    """One row per outcome of "should we generate for this (user, language) today?".
    Returns (kind, sub) where kind is one of:
      not-subscribed | invalid-type | not-due | exists | paused | ready

    Read-only: no LLM calls, no writes. Mirrors the daily-audio generation
    decision table — see docs/history/26-05-30--daily-audio-subscription-state-machine.md."""
    sub = DailyAudioSubscription.find(user, language)
    if sub is None or not sub.enabled:                          return ("not-subscribed", None)
    if sub.lesson_type not in VALID_LESSON_TYPES:               return ("invalid-type",  sub)
    if not sub.scheduled_on(today_local):                       return ("not-due",       sub)
    if generator.today_lesson_exists(user, timezone_offset):    return ("exists",        sub)
    if DailyAudioLesson.waiting_paused_for(user, language.id):  return ("paused",        sub)
    return ("ready", sub)


def generate_for_user(user, lesson_type, raw_suggestion, timezone_offset):
    """Run the full prepare+generate pipeline synchronously for one user.
    Caller must have established via decide_generation() that the user is
    eligible — we don't re-gate here (prepare_lesson_generation still has its
    own existing-lesson check as belt-and-suspenders).

    Returns one of: "generated", "exists", "skipped:<reason>", "failed:<reason>"."""
    try:
        canonical, is_general = resolve_suggestion(user, lesson_type, raw_suggestion)
    except ValueError as e:
        return f"skipped:invalid-subject ({e})"

    result = generator.prepare_lesson_generation(user, timezone_offset, canonical, lesson_type)

    if result.get("lesson_id"):
        return "exists"
    if result.get("error"):
        return f"skipped:{result['error']}"
    if "selected_word_ids" not in result:
        return "failed:unexpected-preparation-result"

    # Rebuild the prepared word objects (prepare returns IDs). .in_() doesn't
    # preserve order, so re-sort to the original selection order.
    selected_words = UserWord.query.filter(UserWord.id.in_(result["selected_word_ids"])).all()
    word_order = {wid: i for i, wid in enumerate(result["selected_word_ids"])}
    selected_words.sort(key=lambda w: word_order.get(w.id, 0))
    unscheduled_words = (
        UserWord.query.filter(UserWord.id.in_(result["unscheduled_word_ids"])).all()
        if result["unscheduled_word_ids"]
        else []
    )
    progress = AudioLessonGenerationProgress.query.get(result["progress_id"])

    def timeout_handler(signum, frame):
        raise TimeoutException("generation timed out")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(PER_USER_TIMEOUT_SECONDS)
    try:
        generator.generate_daily_lesson(
            user=user,
            selected_words=selected_words,
            unscheduled_words=unscheduled_words,
            origin_language=result["origin_language"],
            translation_language=result["translation_language"],
            cefr_level=result["cefr_level"],
            progress=progress,
            raw_suggestion=raw_suggestion,
            canonical_suggestion=canonical,
            lesson_type=lesson_type,
            is_general=is_general,
        )
        db.session.commit()
        return "generated"
    finally:
        signal.alarm(0)


# --- main ---------------------------------------------------------------

if args.user_id:
    user_ids = [args.user_id]
    output(f"Processing single user {args.user_id}...")
else:
    user_ids = User.all_recent_user_ids(DAYS_SINCE_ACTIVE)
    output(f"Finding users active in the last {DAYS_SINCE_ACTIVE} days...")
output("=" * 80)

counts = defaultdict(int)
language_breakdown = defaultdict(int)
start_time = time.time()

for index, user_id in enumerate(user_ids, start=1):
    user = User.find_by_id(user_id)
    if not user:
        continue

    try:
        language = user.learned_language
        timezone_offset = user_timezone_offset_minutes(user)
        today_local = datetime.now(timezone(timedelta(minutes=timezone_offset))).date()

        kind, sub = decide_generation(user, language, timezone_offset, today_local)

        # Dispatch one branch per row of the decision table.
        if kind == "not-subscribed":
            counts["not-subscribed"] += 1
            continue
        if kind == "invalid-type":
            output(f"{index}. {user.name}: invalid lesson_type {sub.lesson_type!r} — skipping")
            counts["skipped"] += 1
            continue
        if kind == "not-due":
            counts["not-due"] += 1
            continue
        if kind == "exists":
            output(f"{index}. {user.name} [{language.name}] — already has today's lesson")
            counts["exists"] += 1
            continue
        if kind == "paused":
            output(f"{index}. {user.name} [{language.name}] — paused (last lesson < 50% listened)")
            counts["paused"] += 1
            continue

        # kind == "ready" — actually generate.
        subject = sub.raw_suggestion or ("study words" if sub.lesson_type == "three_words_lesson" else "?")
        if DRY_RUN:
            output(f"{index}. {user.name} [{language.name}] — WOULD generate {sub.lesson_type}: {subject}")
            counts["would-generate"] += 1
            language_breakdown[language.name] += 1
            continue

        outcome = generate_for_user(user, sub.lesson_type, sub.raw_suggestion, timezone_offset)
        counts[outcome.split(":")[0]] += 1
        if outcome == "generated":
            language_breakdown[user.learned_language.name] += 1
            output(f"{index}. {user.name} [{user.learned_language.name}] — ✓ generated {lesson_type}: {subject}")
        elif outcome == "exists":
            output(f"{index}. {user.name} [{user.learned_language.name}] — already has today's lesson")
        else:
            output(f"{index}. {user.name} [{user.learned_language.name}] — {outcome} ({lesson_type}: {subject})")

    except TimeoutException:
        db.session.rollback()
        counts["failed"] += 1
        output(f"{index}. user {user_id} — ✗ timeout")
    except Exception as e:
        db.session.rollback()
        counts["failed"] += 1
        output(f"{index}. user {user_id} — ✗ error: {e}")
        continue

processing_time = time.time() - start_time

output("\n" + "=" * 80)
output("Daily audio lesson pre-generation summary:")
for key in sorted(counts):
    output(f"  {key}: {counts[key]}")
output(f"  processing time: {processing_time:.1f}s")
if language_breakdown:
    output("\nBy language:")
    for lang, count in sorted(language_breakdown.items(), key=lambda x: x[1], reverse=True):
        output(f"  {lang}: {count}")
if DRY_RUN:
    output("\n[DRY RUN] No lessons were generated.")

if args.send_email:
    email_subject = f"Daily Audio Lesson Pre-generation Report - {datetime.now().strftime('%Y-%m-%d')}"
    if DRY_RUN:
        email_subject += " [DRY RUN]"
    try:
        to_email = app.config.get("PRECOMPUTE_REPORT_EMAIL", app.config.get("SMTP_EMAIL"))
        ZeeguuMailer(email_subject, output_capture.get_output(), to_email).send()
        output(f"\nSummary email sent to {to_email}")
    except Exception as e:
        output(f"\nFailed to send email: {e}")
