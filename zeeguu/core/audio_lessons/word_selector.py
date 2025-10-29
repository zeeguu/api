"""
Shared word selection logic for audio lessons.
This module provides the core algorithm for selecting words for audio lessons,
used by both the main audio lesson generator and analysis tools.
"""

from datetime import datetime, timedelta

from zeeguu.core.model import UserWord, Phrase
from zeeguu.core.model import (
    db,
    User,
    Meaning,
    AudioLessonMeaning,
    DailyAudioLesson,
    DailyAudioLessonSegment,
)
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.core.word_scheduling.basicSR.basicSR import _get_end_of_today
from zeeguu.logging import logp


def get_meanings_already_in_audio_lessons(user: User, days: int = 7) -> set:
    """
    Get the set of meaning IDs that have already been used in recent audio lessons for a user.

    Args:
        user: The user to check
        days: Number of days to look back (default 7)

    Returns:
        Set of meaning IDs
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    meanings_already_in_lessons = (
        db.session.query(Meaning.id)
        .join(AudioLessonMeaning, AudioLessonMeaning.meaning_id == Meaning.id)
        .join(
            DailyAudioLessonSegment,
            DailyAudioLessonSegment.audio_lesson_meaning_id == AudioLessonMeaning.id,
        )
        .join(
            DailyAudioLesson,
            DailyAudioLesson.id == DailyAudioLessonSegment.daily_audio_lesson_id,
        )
        .filter(DailyAudioLesson.user_id == user.id)
        .filter(DailyAudioLesson.created_at >= cutoff_date)
        .distinct()
        .all()
    )

    return {m[0] for m in meanings_already_in_lessons}


def select_words_for_audio_lesson(
    user: User,
    num_words: int = 3,
    language=None,
    log_enabled: bool = True,
    include_recently_learned: bool = True,
    return_unscheduled_info: bool = False,
):
    """
    Select words for an audio lesson. This is the centralized algorithm used by both
    the daily lesson generator and precomputation scripts.

    Strategy:
    1. Prioritize scheduled words due today (need practice)
    2. Fill with other scheduled words if needed (accelerate learning)
    3. If schedule not full, add unscheduled words (introduce new words)
    4. Exclude words used in audio lessons within the last 7 days (provide variety)

    Args:
        user: The user to select words for
        num_words: Number of words to select (default 3)
        language: Language to filter by (optional, defaults to user's learned language)
        log_enabled: Whether to enable logging (default True)
        include_recently_learned: Include words learned in the last 30 days (default True)
        return_unscheduled_info: If True, returns tuple (selected_words, unscheduled_words)

    Returns:
        List of UserWord objects, or empty list if not enough words available
        If return_unscheduled_info=True, returns tuple (selected_words, unscheduled_words)
    """
    # Default to user's learned language if not specified
    if language is None:
        language = user.learned_language

    if log_enabled:
        logp(
            f"[select_words_for_audio_lesson] Getting learning words for user {user.id} in {language.name}"
        )

    # Track which words are unscheduled (for auto-scheduling if pipeline not full)
    unscheduled_word_ids = set()

    # Get meanings already used in recent audio lessons (last 7 days)
    meanings_in_recent_lessons = get_meanings_already_in_audio_lessons(user, days=7)
    if log_enabled and meanings_in_recent_lessons:
        logp(f"[select_words_for_audio_lesson] Excluding {len(meanings_in_recent_lessons)} meanings from recent lessons (last 7 days)")

    # Step 1: Get scheduled words due today (highest priority - need practice!)
    scheduled_due_query = BasicSRSchedule._scheduled_user_words_query(user, language)
    scheduled_due_query = scheduled_due_query.filter(
        BasicSRSchedule.next_practice_time < _get_end_of_today()
    )
    # Exclude words already in recent audio lessons
    if meanings_in_recent_lessons:
        scheduled_due_query = scheduled_due_query.filter(
            ~UserWord.meaning_id.in_(meanings_in_recent_lessons)
        )
    scheduled_due_query = scheduled_due_query.order_by(
        -Phrase.rank.desc(), BasicSRSchedule.cooling_interval.desc()
    )
    learning_words = scheduled_due_query.limit(num_words).all()

    if log_enabled:
        logp(f"[select_words_for_audio_lesson] Found {len(learning_words)} scheduled words due today")

    # Step 2: If not enough, get other scheduled words (accelerate learning)
    if len(learning_words) < num_words:
        more_scheduled_query = BasicSRSchedule._scheduled_user_words_query(user, language)
        # Exclude words we already have
        existing_user_word_ids = [w.id for w in learning_words]
        if existing_user_word_ids:
            more_scheduled_query = more_scheduled_query.filter(
                ~UserWord.id.in_(existing_user_word_ids)
            )
        # Exclude words already in recent audio lessons
        if meanings_in_recent_lessons:
            more_scheduled_query = more_scheduled_query.filter(
                ~UserWord.meaning_id.in_(meanings_in_recent_lessons)
            )
        more_scheduled_query = more_scheduled_query.order_by(-Phrase.rank.desc())
        more_words = more_scheduled_query.limit(num_words - len(learning_words)).all()
        learning_words.extend(more_words)

        if log_enabled:
            logp(f"[select_words_for_audio_lesson] Added {len(more_words)} other scheduled words")

    # Step 3: If schedule not full, add unscheduled words (introduce new words)
    if len(learning_words) < num_words:
        from zeeguu.core.model.user_preference import UserPreference

        # Check if user's schedule has room for more words
        max_words = UserPreference.get_max_words_to_schedule(user)
        current_count = BasicSRSchedule.scheduled_user_words_count(user)
        has_room = current_count < max_words

        if has_room:
            # Get user's unscheduled words for this language
            unscheduled_query = (
                UserWord.query.filter(UserWord.user_id == user.id)
                .filter(UserWord.learned_time == None)  # Not learned
                .filter(UserWord.fit_for_study == 1)  # Fit for study
                .outerjoin(BasicSRSchedule, BasicSRSchedule.user_word_id == UserWord.id)
                .filter(BasicSRSchedule.id == None)  # Not scheduled
                .join(Meaning, UserWord.meaning_id == Meaning.id)
                .join(Phrase, Meaning.origin_id == Phrase.id)
                .filter(Phrase.language_id == language.id)
            )
            # Exclude words we already have
            existing_user_word_ids = [w.id for w in learning_words]
            if existing_user_word_ids:
                unscheduled_query = unscheduled_query.filter(
                    ~UserWord.id.in_(existing_user_word_ids)
                )
            # Exclude words already in recent audio lessons
            if meanings_in_recent_lessons:
                unscheduled_query = unscheduled_query.filter(
                    ~UserWord.meaning_id.in_(meanings_in_recent_lessons)
                )
            # Order by word rank (most important/common words first)
            unscheduled_query = unscheduled_query.order_by(
                -Phrase.rank.desc()  # Negative desc for ascending order (lower rank = more important)
            )
            # Only add as many as there's room for
            room_available = max_words - current_count
            words_needed = num_words - len(learning_words)
            can_add = min(room_available, words_needed)

            unscheduled_words = unscheduled_query.limit(can_add).all()
            learning_words.extend(unscheduled_words)

            # Track these unscheduled words
            unscheduled_word_ids.update(w.id for w in unscheduled_words)

            if log_enabled and unscheduled_words:
                logp(
                    f"[select_words_for_audio_lesson] Added {len(unscheduled_words)} unscheduled words (schedule has room: {current_count}/{max_words})"
                )
        else:
            if log_enabled:
                logp(
                    f"[select_words_for_audio_lesson] Schedule full ({current_count}/{max_words}), not adding unscheduled words"
                )

    # Step 4: If still not enough, get recently learned words (keep reinforcing)
    if len(learning_words) < num_words and include_recently_learned:
        recently_learned_query = (
            UserWord.query.filter(UserWord.user_id == user.id)
            .filter(UserWord.learned_time != None)
            .join(Meaning, UserWord.meaning_id == Meaning.id)
            .join(Phrase, Meaning.origin_id == Phrase.id)
            .filter(Phrase.language_id == language.id)
        )
        # Exclude words we already have in this lesson
        existing_user_word_ids = [w.id for w in learning_words]
        if existing_user_word_ids:
            recently_learned_query = recently_learned_query.filter(
                ~UserWord.id.in_(existing_user_word_ids)
            )
        # Exclude words already in recent audio lessons
        if meanings_in_recent_lessons:
            recently_learned_query = recently_learned_query.filter(
                ~UserWord.meaning_id.in_(meanings_in_recent_lessons)
            )
        recently_learned_query = recently_learned_query.order_by(
            UserWord.learned_time.desc()
        )
        recently_learned = recently_learned_query.limit(
            num_words - len(learning_words)
        ).all()
        learning_words.extend(recently_learned)

        if log_enabled and recently_learned:
            logp(f"[select_words_for_audio_lesson] Added {len(recently_learned)} recently learned words")

    if log_enabled:
        logp(
            f"[select_words_for_audio_lesson] Found {len(learning_words)} words in user's learning queue"
        )

    # Rank words by importance for final selection
    available_words = []
    for user_word in learning_words:
        # Get word rank for importance ranking
        origin_word = user_word.meaning.origin.content
        try:
            from wordstats import Word

            word_stats = Word.stats(origin_word, user_word.meaning.origin.language.code)
            rank = word_stats.rank if word_stats else 999999
        except:
            rank = 999999

        available_words.append((user_word, rank))

    # Sort by rank (lower is more important) and take top N
    available_words.sort(key=lambda x: x[1])
    selected_words = [w[0] for w in available_words[:num_words]]

    if log_enabled:
        logp(
            f"[select_words_for_audio_lesson] Available words after filtering: {len(available_words)}"
        )
        logp(
            f"[select_words_for_audio_lesson] Selected {len(selected_words)} words: {[w.meaning.origin.content for w in selected_words]}"
        )

    if return_unscheduled_info:
        # Return only the unscheduled words from the selected words
        unscheduled_selected = [
            w for w in selected_words if w.id in unscheduled_word_ids
        ]
        return selected_words, unscheduled_selected
    else:
        return selected_words
