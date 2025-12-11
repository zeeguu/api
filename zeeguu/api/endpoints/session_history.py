"""
Session-based history API endpoints.

Provides a chronological view of user learning activities organized by session type:
- Reading sessions: time spent reading articles with translations
- Exercise sessions: practice time with performance metrics
- Browsing sessions: time spent browsing article lists
"""

import flask
from datetime import datetime, timedelta

from . import api, db_session
from zeeguu.api.utils import requires_session, json_result
from zeeguu.core.model import User
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.model.user_exercise_session import UserExerciseSession
from zeeguu.core.model.user_browsing_session import UserBrowsingSession
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.user_activitiy_data import UserActivityData
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.constants import EVENT_ARTICLE_LOST_FOCUS, EVENT_EXERCISE_LOST_FOCUS


def _bookmarks_for_reading_session(session_id, language_id=None):
    """Get all bookmarks created during a reading session."""
    bookmarks = (
        Bookmark.query.filter(Bookmark.reading_session_id == session_id)
        .order_by(Bookmark.time)
        .all()
    )
    result = []
    for b in bookmarks:
        if language_id and b.user_word.meaning.origin.language_id != language_id:
            continue
        result.append({
            "id": b.id,
            "origin": b.user_word.meaning.origin.content,
            "translation": b.user_word.meaning.translation.content,
            "context": b.get_context()[:100] if b.context else None,
        })
    return result


def _bookmarks_for_browsing_session(session_id, language_id=None):
    """Get all bookmarks created during a browsing session."""
    bookmarks = (
        Bookmark.query.filter(Bookmark.browsing_session_id == session_id)
        .order_by(Bookmark.time)
        .all()
    )
    result = []
    for b in bookmarks:
        if language_id and b.user_word.meaning.origin.language_id != language_id:
            continue
        result.append({
            "id": b.id,
            "origin": b.user_word.meaning.origin.content,
            "translation": b.user_word.meaning.translation.content,
        })
    return result


def _words_for_audio_lesson(audio_lesson, language_id=None):
    """Get all words/meanings included in an audio lesson."""
    result = []
    for segment in audio_lesson.segments:
        if segment.segment_type == "meaning_lesson" and segment.audio_lesson_meaning:
            meaning = segment.audio_lesson_meaning.meaning
            if language_id and meaning.origin.language_id != language_id:
                continue
            result.append({
                "origin": meaning.origin.content,
                "translation": meaning.translation.content,
            })
    return result


def _exercises_for_session(session_id, language_id=None):
    """Get exercise summary for an exercise session."""
    exercises = (
        Exercise.query.filter(Exercise.session_id == session_id)
        .order_by(Exercise.time)
        .all()
    )

    words_practiced = []
    correct_count = 0
    total_count = 0

    for ex in exercises:
        # Filter by language if specified
        if language_id and ex.user_word.meaning.origin.language_id != language_id:
            continue
        total_count += 1
        is_correct = ex.is_correct()
        if is_correct:
            correct_count += 1

        # Use preferred_bookmark_id for edit functionality
        bookmark_id = ex.user_word.preferred_bookmark_id

        words_practiced.append(
            {
                "id": bookmark_id,  # Bookmark ID for edit functionality
                "origin": ex.user_word.meaning.origin.content,
                "translation": ex.user_word.meaning.translation.content,
                "correct": is_correct,
            }
        )

    return {
        "words_practiced": words_practiced,
        "total": total_count,
        "correct": correct_count,
        "accuracy": round(correct_count / total_count * 100) if total_count > 0 else 0,
    }


def _count_interruptions(user_id, start_time, end_time, event_type):
    """Count focus-lost events during a session."""
    count = (
        UserActivityData.query
        .filter(UserActivityData.user_id == user_id)
        .filter(UserActivityData.event == event_type)
        .filter(UserActivityData.time >= start_time)
        .filter(UserActivityData.time <= end_time)
        .count()
    )
    return count


def _calculate_focus_level(interruptions, duration_ms, word_count):
    """
    Calculate a focus level based on interruptions, duration, and engagement.

    Returns: 'focused', 'moderate', or 'distracted'
    """
    if duration_ms is None or duration_ms == 0:
        return None

    # Calculate words per minute as engagement metric
    duration_min = duration_ms / 60000
    words_per_min = word_count / duration_min if duration_min > 0 else 0

    # Interruptions per 10 minutes
    interruptions_per_10min = (interruptions / duration_min) * 10 if duration_min > 0 else 0

    # Focus level based on interruptions
    if interruptions <= 1 and interruptions_per_10min < 2:
        return "focused"
    elif interruptions <= 3 or interruptions_per_10min < 4:
        return "moderate"
    else:
        return "distracted"


@api.route("/session_history", methods=["GET"])
@requires_session
def session_history():
    """
    Get session-based history for the current user.

    Query params:
        days: number of days to look back (default: 7, max: 30)
        from_date: ISO date string for custom range start
        to_date: ISO date string for custom range end

    Returns a list of sessions ordered by start_time descending, grouped by date.
    Each session includes:
        - session_type: 'reading', 'exercise', or 'browsing'
        - start_time: ISO timestamp
        - duration: in milliseconds
        - words: list of words translated/practiced
        - For reading: article_title
        - For exercise: performance summary
    """
    user = User.find_by_id(flask.g.user_id)
    learned_language = user.learned_language

    # Handle date range - either from_date/to_date or days
    from_date_str = flask.request.args.get("from_date")
    to_date_str = flask.request.args.get("to_date")

    if from_date_str and to_date_str:
        from_date = datetime.fromisoformat(from_date_str.replace('Z', '+00:00')).replace(tzinfo=None)
        to_date = datetime.fromisoformat(to_date_str.replace('Z', '+00:00')).replace(tzinfo=None)
    else:
        days = min(int(flask.request.args.get("days", 7)), 30)
        from_date = datetime.now() - timedelta(days=days)
        to_date = datetime.now()

    # Fetch all session types
    reading_sessions = UserReadingSession.find_by_user(
        user.id, from_date=from_date.isoformat()
    )
    exercise_sessions = UserExerciseSession.find_by_user_id(
        user.id, from_date=from_date.isoformat()
    )
    browsing_sessions = UserBrowsingSession.find_by_user(
        user.id, from_date=from_date.isoformat()
    )

    sessions = []

    def format_duration(duration_ms):
        """Format duration showing seconds for short durations, minutes for longer ones."""
        if duration_ms is None or duration_ms == 0:
            return "0 sec"
        seconds = duration_ms / 1000
        if seconds < 60:
            return f"{int(seconds)} sec"
        minutes = seconds / 60
        if minutes < 60:
            return f"{round(minutes, 1)} min"
        hours = minutes / 60
        return f"{round(hours, 1)} hr"

    # Process reading sessions
    for rs in reading_sessions:
        # Skip sessions with no duration (abandoned/not properly closed)
        if not rs.duration:
            continue
        # Filter by learned language
        if rs.article and rs.article.language_id != learned_language.id:
            continue
        bookmarks = _bookmarks_for_reading_session(rs.id, learned_language.id)

        # Count interruptions (focus lost events during this session)
        end_time = rs.last_action_time if rs.last_action_time else rs.start_time
        interruptions = _count_interruptions(
            user.id, rs.start_time, end_time, EVENT_ARTICLE_LOST_FOCUS
        )
        focus_level = _calculate_focus_level(interruptions, rs.duration, len(bookmarks))

        # reading_source is stored directly on the session ('extension' or 'web')
        # Will be None for historical sessions created before this field was added
        reading_source = rs.reading_source

        sessions.append(
            {
                "session_type": "reading",
                "start_time": rs.start_time.isoformat(),
                "duration": rs.duration,
                "duration_readable": format_duration(rs.duration),
                "article_id": rs.article_id,
                "article_title": rs.article.title if rs.article else None,
                "reading_source": reading_source,
                "words": bookmarks,
                "word_count": len(bookmarks),
                "interruptions": interruptions,
                "focus_level": focus_level,
            }
        )

    # Process exercise sessions
    for es in exercise_sessions:
        exercise_data = _exercises_for_session(es.id, learned_language.id)
        # Only include sessions with exercises in the learned language
        if exercise_data["total"] > 0:
            # Count interruptions (focus lost events during this session)
            end_time = es.last_action_time if es.last_action_time else es.start_time
            interruptions = _count_interruptions(
                user.id, es.start_time, end_time, EVENT_EXERCISE_LOST_FOCUS
            )
            focus_level = _calculate_focus_level(
                interruptions, es.duration, exercise_data["total"]
            )

            sessions.append(
                {
                    "session_type": "exercise",
                    "start_time": es.start_time.isoformat(),
                    "duration": es.duration,
                    "duration_readable": format_duration(es.duration),
                    "words": exercise_data["words_practiced"],
                    "word_count": exercise_data["total"],
                    "correct_count": exercise_data["correct"],
                    "accuracy": exercise_data["accuracy"],
                    "interruptions": interruptions,
                    "focus_level": focus_level,
                }
            )

    # Process browsing sessions
    for bs in browsing_sessions:
        bookmarks = _bookmarks_for_browsing_session(bs.id, learned_language.id)
        if bookmarks:  # Only include browsing sessions with translations in learned language
            sessions.append(
                {
                    "session_type": "browsing",
                    "start_time": bs.start_time.isoformat(),
                    "duration": bs.duration,
                    "duration_readable": format_duration(bs.duration),
                    "words": bookmarks,
                    "word_count": len(bookmarks),
                }
            )

    # Process audio lessons
    audio_lessons = (
        DailyAudioLesson.query
        .filter(DailyAudioLesson.user_id == user.id)
        .filter(DailyAudioLesson.language_id == learned_language.id)
        .filter(DailyAudioLesson.recommended_at >= from_date)
        .filter(DailyAudioLesson.recommended_at <= to_date)
        .filter(DailyAudioLesson.listened_count > 0)  # Only include lessons that were actually played
        .all()
    )

    for al in audio_lessons:
        words = _words_for_audio_lesson(al, learned_language.id)
        # Convert duration from seconds to milliseconds for consistency
        duration_ms = (al.duration_seconds or 0) * 1000

        sessions.append(
            {
                "session_type": "audio",
                "start_time": al.recommended_at.isoformat(),
                "duration": duration_ms,
                "duration_readable": format_duration(duration_ms),
                "words": words,
                "word_count": len(words),
                "completed": al.is_completed,
                "listened_count": al.listened_count,
            }
        )

    # Sort by start_time descending
    sessions.sort(key=lambda s: s["start_time"], reverse=True)

    return json_result(sessions)
