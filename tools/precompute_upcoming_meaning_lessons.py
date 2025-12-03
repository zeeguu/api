#!/usr/bin/env python

"""
Script that precomputes audio lessons for recently active users.
It generates audio lessons for their next three meanings across all languages they're learning.
Users are prioritized by most recent activity.
Uses shared logic from DailyLessonGenerator to avoid code duplication.

Usage:
    python precompute_upcoming_meaning_lessons.py [--send-email] [--dry-run] [--days N]
"""

import sys
import argparse
from datetime import datetime

# Parse command line arguments
parser = argparse.ArgumentParser(
    description="Precompute audio lessons for active users"
)
parser.add_argument(
    "--send-email", action="store_true", help="Send summary email after completion"
)
parser.add_argument(
    "--dry-run", action="store_true", help="Run without actually generating audio files"
)
parser.add_argument(
    "--days",
    type=int,
    default=30,
    help="Number of days to consider for active users (default: 30)",
)
args = parser.parse_args()

DAYS_SINCE_ACTIVE = args.days
SHOW_DETAILS = True
DRY_RUN = args.dry_run

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

import time
from collections import defaultdict

from zeeguu.core.model import User, db, AudioLessonMeaning
from zeeguu.core.model.user_activitiy_data import UserActivityData
from zeeguu.core.audio_lessons.word_selector import (
    select_words_for_audio_lesson,
)
from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator
from zeeguu.core.audio_lessons.voice_config import is_language_supported_for_audio
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

# Initialize daily lesson generator (contains the audio generation logic)
lesson_generator = DailyLessonGenerator()


# Create a custom output handler that captures all output
class OutputCapture:
    def __init__(self):
        self.output = []

    def write(self, text):
        # Write to stdout
        print(text, end="")
        # Capture for email
        self.output.append(text)

    def get_output(self):
        return "".join(self.output)


output_capture = OutputCapture()


# Helper function to make output easier
def output(text=""):
    output_capture.write(text + "\n")


def get_precomputed_meanings_count(user, language):
    """
    Get the count of already precomputed audio lesson meanings
    for the user's next lesson in this language.

    Returns:
        tuple: (precomputed_count, next_words)
        - precomputed_count: number of next words that already have audio lessons
        - next_words: the actual next words that would be selected for a lesson
    """
    # Get the next words that would be selected for a lesson
    next_words = select_words_for_audio_lesson(
        user, num_words=3, language=language, log_enabled=False
    )

    if len(next_words) < 2:
        # User doesn't have enough words for a lesson anyway
        return (-1, next_words)  # Return -1 to indicate "not enough words"

    # Check how many of these next words already have precomputed audio lessons
    precomputed_count = 0
    for user_word in next_words:
        existing_lesson = AudioLessonMeaning.find_by_meaning(user_word.meaning)
        if existing_lesson:
            precomputed_count += 1

    return (precomputed_count, next_words)


def generate_audio_lesson_for_meaning(user, user_word, cefr_level="B1", timeout_seconds=600):
    """
    Generate an audio lesson for a specific meaning using the shared logic.

    Args:
        user: The user who owns this meaning
        user_word: The UserWord object containing the meaning
        cefr_level: CEFR level for the lesson
        timeout_seconds: Maximum time to spend generating this lesson (default: 10 minutes)

    Returns:
        AudioLessonMeaning object or None if generation fails
    """
    meaning = user_word.meaning
    origin_language = meaning.origin.language.code
    translation_language = meaning.translation.language.code

    # Helper function to get display info
    def get_word_display_info():
        origin_word = meaning.origin.content
        try:
            from wordstats import Word

            word_stats = Word.stats(origin_word, meaning.origin.language.code)
            rank = word_stats.rank if word_stats else "N/A"
        except:
            rank = "N/A"

        # Determine scheduling status
        from zeeguu.core.word_scheduling.basicSR.basicSR import (
            BasicSRSchedule,
            _get_end_of_today,
        )

        if user_word.is_learned():
            status = "learned"
        else:
            scheduled_today = BasicSRSchedule.query.filter(
                BasicSRSchedule.user_word_id == user_word.id,
                BasicSRSchedule.next_practice_time < _get_end_of_today(),
            ).first()
            if scheduled_today:
                status = "scheduled_today"
            else:
                scheduled = BasicSRSchedule.query.filter(
                    BasicSRSchedule.user_word_id == user_word.id
                ).first()
                status = "scheduled" if scheduled else "unscheduled"
        return rank, status

    # Check if audio lesson already exists
    existing_lesson = AudioLessonMeaning.find_by_meaning(meaning)
    if existing_lesson:
        if SHOW_DETAILS:
            rank, status = get_word_display_info()
            output(
                f"        Audio lesson already exists for: {meaning.origin.content} → {meaning.translation.content} (rank: {rank}, {status})"
            )
        return existing_lesson

    if DRY_RUN:
        rank, status = get_word_display_info()
        output(
            f"        [DRY RUN] Would generate audio for: {meaning.origin.content} → {meaning.translation.content} (rank: {rank}, {status})"
        )
        return None

    try:
        import signal

        class TimeoutException(Exception):
            pass

        def timeout_handler(signum, frame):
            raise TimeoutException("Audio lesson generation timed out")

        # Set up timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)

        try:
            # Use the shared generation logic from DailyLessonGenerator
            audio_lesson_meaning = lesson_generator.generate_audio_lesson_meaning(
                user_word,
                origin_language,
                translation_language,
                cefr_level,
                "claude-v1",
            )

            db.session.commit()

            if SHOW_DETAILS:
                rank, status = get_word_display_info()
                output(
                    f"        ✓ Generated audio lesson for: {meaning.origin.content} → {meaning.translation.content} (rank: {rank}, {status}, {audio_lesson_meaning.duration_seconds}s)"
                )

            return audio_lesson_meaning

        finally:
            # Cancel the alarm
            signal.alarm(0)

    except TimeoutException:
        db.session.rollback()
        output(
            f"        ✗ Timeout (>{timeout_seconds}s) generating audio for {meaning.origin.content}"
        )
        return None
    except Exception as e:
        db.session.rollback()
        output(
            f"        ✗ Failed to generate audio for {meaning.origin.content}: {str(e)}"
        )
        return None


# Get users with their last activity time
output(f"Finding users active in the last {DAYS_SINCE_ACTIVE} days...")
output()

user_activity_map = []
for user_id in User.all_recent_user_ids(DAYS_SINCE_ACTIVE):
    user = User.find_by_id(user_id)
    last_activity = UserActivityData.get_last_activity_timestamp(user.id)
    user_activity_map.append((user, last_activity))

# Sort users by most recent activity
user_activity_map.sort(key=lambda x: x[1], reverse=True)

output(f"Processing {len(user_activity_map)} users (sorted by most recent activity)...")
output("=" * 80)
output()

total_users = 0
total_meanings_processed = 0
total_audio_generated = 0
total_audio_existing = 0
total_failures = 0
language_breakdown = defaultdict(int)

start_time = time.time()

for user, last_activity in user_activity_map:
    total_users += 1

    try:
        output(
            f"\n{total_users}. {user.name} (last active: {last_activity.strftime('%Y-%m-%d')})"
        )
        output(f"   Main language: {user.learned_language.name}")

        # Get user's CEFR level
        cefr_level = user.cefr_level_for_learned_language()

        # Get all languages for this user
        user_languages = user.get_all_languages()
        user_meanings_count = 0

        for language in user_languages:
            try:
                # Check if language is supported for audio generation
                if not is_language_supported_for_audio(language.code):
                    output(
                        f"   [{language.name}] Skipping - audio not supported for this language"
                    )
                    continue

                # Check how many meanings are already precomputed for next lesson
                precomputed_count, next_words = get_precomputed_meanings_count(
                    user, language
                )

                if precomputed_count == -1:
                    output(
                        f"   [{language.name}] Not enough words available for lessons (need at least 2, has {len(next_words)})"
                    )
                    continue

                if precomputed_count >= 3:
                    if SHOW_DETAILS and next_words:
                        # Show the precomputed meanings
                        precomputed_meanings = []
                        for user_word in next_words[
                            :3
                        ]:  # Show first 3 (the ones for next lesson)
                            existing_lesson = AudioLessonMeaning.find_by_meaning(
                                user_word.meaning
                            )
                            if existing_lesson:
                                meaning = user_word.meaning
                                try:
                                    from wordstats import Word

                                    word_stats = Word.stats(
                                        meaning.origin.content, meaning.origin.language.code
                                    )
                                    rank = word_stats.rank if word_stats else "N/A"
                                except:
                                    rank = "N/A"

                                # Determine scheduling status
                                from zeeguu.core.word_scheduling.basicSR.basicSR import (
                                    BasicSRSchedule,
                                    _get_end_of_today,
                                )

                                if user_word.is_learned():
                                    status = "learned"
                                else:
                                    scheduled_today = BasicSRSchedule.query.filter(
                                        BasicSRSchedule.user_word_id == user_word.id,
                                        BasicSRSchedule.next_practice_time
                                        < _get_end_of_today(),
                                    ).first()
                                    if scheduled_today:
                                        status = "scheduled_today"
                                    else:
                                        scheduled = BasicSRSchedule.query.filter(
                                            BasicSRSchedule.user_word_id == user_word.id
                                        ).first()
                                        status = "scheduled" if scheduled else "unscheduled"

                                precomputed_meanings.append(
                                    f"{meaning.origin.content} → {meaning.translation.content} (rank: {rank}, {status})"
                                )

                        if precomputed_meanings:
                            output(
                                f"   [{language.name}] Already has the following precomputed meanings for next lesson:"
                            )
                            for meaning_info in precomputed_meanings:
                                output(f"        ✓ {meaning_info}")
                        else:
                            output(
                                f"   [{language.name}] Already has enough precomputed meanings for next lesson"
                            )
                    else:
                        output(
                            f"   [{language.name}] Already has enough precomputed meanings for next lesson"
                        )
                    continue

                # Only process the words that don't have audio lessons yet
                words_to_process = []
                for user_word in next_words:
                    existing_lesson = AudioLessonMeaning.find_by_meaning(user_word.meaning)
                    if not existing_lesson:
                        words_to_process.append(user_word)

                if words_to_process:
                    output(
                        f"   [{language.name}] Has {precomputed_count}/3 precomputed, processing {len(words_to_process)} more meanings:"
                    )

                    for user_word in words_to_process:
                        total_meanings_processed += 1
                        user_meanings_count += 1
                        language_breakdown[language.name] += 1

                        # Generate audio lesson for this meaning
                        audio_lesson = generate_audio_lesson_for_meaning(
                            user, user_word, cefr_level
                        )

                        if audio_lesson:
                            if (
                                hasattr(audio_lesson, "created_by")
                                and audio_lesson.created_by == "claude-v1"
                            ):
                                total_audio_generated += 1
                            else:
                                total_audio_existing += 1
                        elif not DRY_RUN:
                            total_failures += 1

            except Exception as language_error:
                output(f"   [{language.name}] Error processing language: {str(language_error)}")
                # Continue with next language
                continue

        if user_meanings_count == 0:
            output("   No meanings to process")

    except Exception as e:
        output(f"   ✗ Error processing user {user.name}: {str(e)}")
        import traceback
        output(f"   Traceback: {traceback.format_exc()}")
        # Continue with next user
        continue

# Summary
end_time = time.time()
processing_time = end_time - start_time

output("\n" + "=" * 80)
output(f"\nPrecomputation Summary:")
output(f"  Total users processed: {total_users}")
output(f"  Total meanings processed: {total_meanings_processed}")
if not DRY_RUN:
    output(f"  Audio lessons generated: {total_audio_generated}")
    output(f"  Audio lessons already existing: {total_audio_existing}")
    output(f"  Failed generations: {total_failures}")
output(f"  Processing time: {processing_time:.1f} seconds")

output(f"\nBreakdown by language:")
for lang, count in sorted(language_breakdown.items(), key=lambda x: x[1], reverse=True):
    output(f"  {lang}: {count} meanings")

if DRY_RUN:
    output(f"\n[DRY RUN MODE] No audio files were actually generated.")
    output(f"Set DRY_RUN = False to generate audio lessons.")

# Send email if requested
if args.send_email:
    output("\n" + "=" * 80)
    output("Sending summary email...")

    email_content = output_capture.get_output()
    email_subject = (
        f"Audio Lesson Precomputation Report - {datetime.now().strftime('%Y-%m-%d')}"
    )

    if DRY_RUN:
        email_subject += " [DRY RUN]"

    # Add summary at the top of email
    email_body = f"""Audio Lesson Precomputation Summary
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Quick Stats:
- Users processed: {total_users}
- Meanings processed: {total_meanings_processed}
- Audio generated: {total_audio_generated if not DRY_RUN else 'N/A (dry run)'}
- Failures: {total_failures if not DRY_RUN else 'N/A (dry run)'}
- Processing time: {processing_time:.1f} seconds

Full Output:
{'=' * 80}

{email_content}
"""

    try:
        to_email = app.config.get(
            "PRECOMPUTE_REPORT_EMAIL", app.config.get("SMTP_EMAIL")
        )
        mailer = ZeeguuMailer(email_subject, email_body, to_email)
        mailer.send()
        output(f"Summary email sent to {to_email}")
    except Exception as e:
        output(f"Failed to send email: {str(e)}")
