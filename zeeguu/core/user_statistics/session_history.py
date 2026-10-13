"""
A learner's activity as a list of sessions: reading, exercises, browsing and
audio lessons. Shown to the learner on Activity -> History, and to their
teacher for the class's language.
"""

from zeeguu.core.constants import EVENT_ARTICLE_LOST_FOCUS, EVENT_EXERCISE_LOST_FOCUS
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.user_activitiy_data import UserActivityData
from zeeguu.core.model.user_browsing_session import UserBrowsingSession
from zeeguu.core.model.user_exercise_session import UserExerciseSession
from zeeguu.core.model.user_listening_session import UserListeningSession
from zeeguu.core.model.user_reading_session import UserReadingSession

# What the learner sees is a glimpse of the sentence; the teacher sees it whole.
LEARNER_CONTEXT_LENGTH = 100


def _practised_user_word_ids(user_word_ids):
    if not user_word_ids:
        return set()
    rows = (
        Exercise.query.with_entities(Exercise.user_word_id)
        .filter(Exercise.user_word_id.in_(user_word_ids))
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


def _bookmarks_in_session(session_filter, language_id, for_teacher, with_context):
    bookmarks = Bookmark.query.filter(session_filter).order_by(Bookmark.time).all()
    bookmarks = [
        b for b in bookmarks
        if b.user_word.meaning.origin.language_id == language_id
    ]
    practised = (
        _practised_user_word_ids([b.user_word_id for b in bookmarks])
        if for_teacher
        else set()
    )

    result = []
    for b in bookmarks:
        word = {
            "id": b.id,
            "origin": b.user_word.meaning.origin.content,
            "translation": b.user_word.meaning.translation.content,
        }
        if with_context:
            context = b.get_context() if b.context else None
            if context and not for_teacher:
                context = context[:LEARNER_CONTEXT_LENGTH]
            word["context"] = context
        if for_teacher:
            word["practised"] = b.user_word_id in practised
        result.append(word)
    return result


def _words_for_audio_lesson(audio_lesson, language_id):
    """Get all words/meanings included in an audio lesson."""
    result = []
    for segment in audio_lesson.segments:
        if segment.segment_type == "meaning_lesson" and segment.audio_lesson_meaning:
            meaning = segment.audio_lesson_meaning.meaning
            if meaning.origin.language_id != language_id:
                continue
            result.append({
                "origin": meaning.origin.content,
                "translation": meaning.translation.content,
            })
    return result


def _exercises_for_session(session_id, language_id):
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
        if ex.user_word.meaning.origin.language_id != language_id:
            continue
        total_count += 1
        # Same definition as the teacher's "correct on 1st try"
        is_correct = ExerciseOutcome.is_correct_on_first_try(ex.outcome.outcome)
        if is_correct:
            correct_count += 1

        words_practiced.append(
            {
                # preferred bookmark, so the learner can edit the word
                "id": ex.user_word.preferred_bookmark_id,
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
    return (
        UserActivityData.query
        .filter(UserActivityData.user_id == user_id)
        .filter(UserActivityData.event == event_type)
        .filter(UserActivityData.time >= start_time)
        .filter(UserActivityData.time <= end_time)
        .count()
    )


def _calculate_focus_level(interruptions, duration_ms):
    """
    Calculate a focus level based on interruptions and duration.

    Returns: 'focused', 'moderate', or 'distracted'
    """
    if duration_ms is None or duration_ms == 0:
        return None

    duration_min = duration_ms / 60000
    interruptions_per_10min = (interruptions / duration_min) * 10 if duration_min > 0 else 0

    if interruptions <= 1 and interruptions_per_10min < 2:
        return "focused"
    elif interruptions <= 3 or interruptions_per_10min < 4:
        return "moderate"
    else:
        return "distracted"


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


def _reading_sessions(user_id, language_id, from_date, to_date, for_teacher):
    sessions = []
    for rs in UserReadingSession.find_by_user(user_id, from_date, to_date):
        # Skip sessions with no duration (abandoned/not properly closed)
        if not rs.duration:
            continue
        if rs.article and rs.article.language_id != language_id:
            continue
        bookmarks = _bookmarks_in_session(
            Bookmark.reading_session_id == rs.id, language_id, for_teacher, True
        )

        end_time = rs.last_action_time if rs.last_action_time else rs.start_time
        interruptions = _count_interruptions(
            user_id, rs.start_time, end_time, EVENT_ARTICLE_LOST_FOCUS
        )

        sessions.append(
            {
                "session_type": "reading",
                "start_time": rs.start_time.isoformat(),
                "duration": rs.duration,
                "duration_readable": format_duration(rs.duration),
                "article_id": rs.article_id,
                "article_title": rs.article.title if rs.article else None,
                "article_word_count": rs.article.word_count if rs.article else None,
                "article_difficulty": rs.article.fk_difficulty if rs.article else None,
                # 'extension' or 'web'; None for sessions from before the field existed
                "reading_source": rs.reading_source,
                "words": bookmarks,
                "word_count": len(bookmarks),
                "interruptions": interruptions,
                "focus_level": _calculate_focus_level(interruptions, rs.duration),
            }
        )
    return sessions


def _exercise_sessions(user_id, language_id, from_date, to_date):
    sessions = []
    for es in UserExerciseSession.find_by_user_id(user_id, from_date, to_date):
        exercise_data = _exercises_for_session(es.id, language_id)
        # Only include sessions with exercises in this language
        if exercise_data["total"] == 0:
            continue
        end_time = es.last_action_time if es.last_action_time else es.start_time
        interruptions = _count_interruptions(
            user_id, es.start_time, end_time, EVENT_EXERCISE_LOST_FOCUS
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
                "focus_level": _calculate_focus_level(interruptions, es.duration),
            }
        )
    return sessions


def _browsing_sessions(user_id, language_id, from_date, to_date, for_teacher):
    sessions = []
    for bs in UserBrowsingSession.find_by_user(user_id, from_date, to_date):
        # Browsing without translating (previews, search) still counts:
        # a student who browsed but never opened an article must not look idle.
        if not bs.duration:
            continue
        # language_id is the learned language when the session started
        if bs.language_id is not None and bs.language_id != language_id:
            continue
        bookmarks = _bookmarks_in_session(
            Bookmark.browsing_session_id == bs.id, language_id, for_teacher, for_teacher
        )
        # Older sessions have no language; their translations are all we have to go on
        if bs.language_id is None and not bookmarks:
            continue
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
    return sessions


def _audio_sessions(user_id, language_id, from_date, to_date):
    sessions = []
    listening_sessions = UserListeningSession.find_by_user_and_language(
        user_id, language_id, from_date, to_date
    )
    for ls in listening_sessions:
        if not ls.duration:
            continue
        audio_lesson = ls.daily_audio_lesson
        is_completed = audio_lesson.is_completed if audio_lesson else False

        # Only show words for completed lessons (incomplete = unknown coverage)
        words = _words_for_audio_lesson(audio_lesson, language_id) if is_completed else []

        sessions.append(
            {
                "session_type": "audio",
                "start_time": ls.start_time.isoformat(),
                "duration": ls.duration,  # Already in milliseconds
                "duration_readable": format_duration(ls.duration),
                "words": words,
                "word_count": len(words),
                "completed": is_completed,
                "lesson_id": audio_lesson.id if audio_lesson else None,
                "lesson_title": audio_lesson.display_title() if audio_lesson else None,
            }
        )
    return sessions


def session_history(user_id, language_id, from_date, to_date, for_teacher=False):
    """
    All sessions in [from_date, to_date] in the given language, newest first.

    for_teacher: translated words carry their full sentence and whether the
    student practised them since; browsing sessions list their words with
    context too.
    """
    sessions = (
        _reading_sessions(user_id, language_id, from_date, to_date, for_teacher)
        + _exercise_sessions(user_id, language_id, from_date, to_date)
        + _browsing_sessions(user_id, language_id, from_date, to_date, for_teacher)
        + _audio_sessions(user_id, language_id, from_date, to_date)
    )
    sessions.sort(key=lambda s: s["start_time"], reverse=True)
    return sessions
