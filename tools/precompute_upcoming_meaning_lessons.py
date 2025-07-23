#!/usr/bin/env python

"""
Script that precomputes audio lessons for recently active users.
It generates audio lessons for their next three meanings across all languages they're learning.
Users are prioritized by most recent activity.
Uses shared logic from DailyLessonGenerator to avoid code duplication.
"""

DAYS_SINCE_ACTIVE = 30
SHOW_DETAILS = True
DRY_RUN = True  # Set to True to see what would be generated without actually generating

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

# Initialize daily lesson generator (contains the audio generation logic)
lesson_generator = DailyLessonGenerator()


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


def generate_audio_lesson_for_meaning(user, user_word, cefr_level="B1"):
    """
    Generate an audio lesson for a specific meaning using the shared logic.

    Args:
        user: The user who owns this meaning
        user_word: The UserWord object containing the meaning
        cefr_level: CEFR level for the lesson

    Returns:
        AudioLessonMeaning object or None if generation fails
    """
    meaning = user_word.meaning
    origin_language = meaning.origin.language.code
    translation_language = meaning.translation.language.code

    # Helper function to get display info
    # Check if audio lesson already exists
    existing_lesson = AudioLessonMeaning.find_by_meaning(meaning)
    if existing_lesson:
        if SHOW_DETAILS:
            rank, status = get_word_display_info()
            print(
                f"        Audio lesson already exists for: {meaning.origin.content} → {meaning.translation.content} (rank: {rank}, {status})"
            )
        return existing_lesson

    if DRY_RUN:
        rank, status = get_word_display_info()
        print(
            f"        [DRY RUN] Would generate audio for: {meaning.origin.content} → {meaning.translation.content} (rank: {rank}, {status})"
        )
        return None

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
            print(
                f"        ✓ Generated audio lesson for: {meaning.origin.content} → {meaning.translation.content} (rank: {rank}, {status}, {audio_lesson_meaning.duration_seconds}s)"
            )

        return audio_lesson_meaning

    except Exception as e:
        db.session.rollback()
        print(
            f"        ✗ Failed to generate audio for {meaning.origin.content}: {str(e)}"
        )
        return None


# Get users with their last activity time
print(f"Finding users active in the last {DAYS_SINCE_ACTIVE} days...")
print("")

user_activity_map = []
for user_id in User.all_recent_user_ids(DAYS_SINCE_ACTIVE):
    user = User.find_by_id(user_id)
    last_activity = UserActivityData.get_last_activity_timestamp(user.id)
    user_activity_map.append((user, last_activity))

# Sort users by most recent activity
user_activity_map.sort(key=lambda x: x[1], reverse=True)

print(f"Processing {len(user_activity_map)} users (sorted by most recent activity)...")
print("=" * 80)
print("")

total_users = 0
total_meanings_processed = 0
total_audio_generated = 0
total_audio_existing = 0
total_failures = 0
language_breakdown = defaultdict(int)

start_time = time.time()

for user, last_activity in user_activity_map:
    total_users += 1
    print(
        f"\n{total_users}. {user.name} (last active: {last_activity.strftime('%Y-%m-%d')})"
    )
    print(f"   Main language: {user.learned_language.name}")

    # Get user's CEFR level
    cefr_level = user.cefr_level_for_learned_language()

    # Get all languages for this user
    try:
        user_languages = user.get_all_languages()
        user_meanings_count = 0

        for language in user_languages:
            # Check how many meanings are already precomputed for next lesson
            precomputed_count, next_words = get_precomputed_meanings_count(
                user, language
            )

            if precomputed_count == -1:
                print(
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
                        print(
                            f"   [{language.name}] Already has enough precomputed meanings for next lesson:"
                        )
                        for meaning_info in precomputed_meanings:
                            print(f"        ✓ {meaning_info}")
                    else:
                        print(
                            f"   [{language.name}] Already has enough precomputed meanings for next lesson"
                        )
                else:
                    print(
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
                print(
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

        if user_meanings_count == 0:
            print("   No meanings to process")

    except Exception as e:
        print(f"   Error processing user: {str(e)}")

# Summary
end_time = time.time()
processing_time = end_time - start_time

print("\n" + "=" * 80)
print(f"\nPrecomputation Summary:")
print(f"  Total users processed: {total_users}")
print(f"  Total meanings processed: {total_meanings_processed}")
if not DRY_RUN:
    print(f"  Audio lessons generated: {total_audio_generated}")
    print(f"  Audio lessons already existing: {total_audio_existing}")
    print(f"  Failed generations: {total_failures}")
print(f"  Processing time: {processing_time:.1f} seconds")

print(f"\nBreakdown by language:")
for lang, count in sorted(language_breakdown.items(), key=lambda x: x[1], reverse=True):
    print(f"  {lang}: {count} meanings")

if DRY_RUN:
    print(f"\n[DRY RUN MODE] No audio files were actually generated.")
    print(f"Set DRY_RUN = False to generate audio lessons.")


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
