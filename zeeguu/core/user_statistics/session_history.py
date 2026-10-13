"""
A learner's activity as a list of sessions: reading, exercises, browsing and
audio lessons. Shown to the learner on Activity -> History, and to their
teacher for the class's language.

The range is unbounded (a teacher may look at a whole school year), so each
kind of detail is fetched with one query for all sessions, not one per session.
"""

from bisect import bisect_left, bisect_right
from collections import defaultdict

from sqlalchemy.orm import joinedload

from zeeguu.core.constants import EVENT_ARTICLE_LOST_FOCUS, EVENT_EXERCISE_LOST_FOCUS
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user_activitiy_data import UserActivityData
from zeeguu.core.model.user_browsing_session import UserBrowsingSession
from zeeguu.core.model.user_exercise_session import UserExerciseSession
from zeeguu.core.model.user_listening_session import UserListeningSession
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.model.user_word import UserWord

# What the learner sees is a glimpse of the sentence; the teacher sees it whole.
LEARNER_CONTEXT_LENGTH = 100


def _with_meaning(user_word_relationship):
    meaning = user_word_relationship.joinedload(UserWord.meaning)
    return [
        meaning.joinedload(Meaning.origin),
        meaning.joinedload(Meaning.translation),
    ]


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


def _words_by_session(session_column, session_ids, language_id, for_teacher, with_context):
    """
    {session id: [translated word]} for the bookmarks made in those sessions.
    """
    if not session_ids:
        return {}

    options = _with_meaning(joinedload(Bookmark.user_word))
    if with_context:
        options += [
            joinedload(Bookmark.context).joinedload(BookmarkContext.text),
            joinedload(Bookmark.text),
        ]
    bookmarks = [
        b
        for b in Bookmark.query.options(*options)
        .filter(session_column.in_(session_ids))
        .order_by(Bookmark.time)
        .all()
        if b.user_word.meaning.origin.language_id == language_id
    ]
    practised = (
        _practised_user_word_ids({b.user_word_id for b in bookmarks})
        if for_teacher
        else set()
    )

    result = defaultdict(list)
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
        result[getattr(b, session_column.key)].append(word)
    return result


class _Interruptions:
    """Focus-lost events of one kind, fetched once and counted per session."""

    def __init__(self, user_id, event_type, sessions):
        self.times = []
        if not sessions:
            return
        earliest = min(s.start_time for s in sessions)
        latest = max(_end_time(s) for s in sessions)
        rows = (
            UserActivityData.query.with_entities(UserActivityData.time)
            .filter(UserActivityData.user_id == user_id)
            .filter(UserActivityData.event == event_type)
            .filter(UserActivityData.time >= earliest)
            .filter(UserActivityData.time <= latest)
            .all()
        )
        self.times = sorted(row[0] for row in rows)

    def during(self, session):
        return bisect_right(self.times, _end_time(session)) - bisect_left(
            self.times, session.start_time
        )


def _end_time(session):
    return session.last_action_time if session.last_action_time else session.start_time


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
    candidates = (
        UserReadingSession.query.options(joinedload(UserReadingSession.article))
        .filter(UserReadingSession.user_id == user_id)
        .filter(UserReadingSession.start_time >= from_date)
        .filter(UserReadingSession.start_time <= to_date)
        .all()
    )
    reading_sessions = [
        rs
        for rs in candidates
        # no duration: abandoned / never closed; no article: language unknown
        if rs.duration and rs.article and rs.article.language_id == language_id
    ]
    words = _words_by_session(
        Bookmark.reading_session_id,
        [rs.id for rs in reading_sessions],
        language_id,
        for_teacher,
        with_context=True,
    )
    interruptions = _Interruptions(user_id, EVENT_ARTICLE_LOST_FOCUS, reading_sessions)

    sessions = []
    for rs in reading_sessions:
        bookmarks = words.get(rs.id, [])
        count = interruptions.during(rs)
        sessions.append(
            {
                "session_type": "reading",
                "start_time": rs.start_time.isoformat(),
                "duration": rs.duration,
                "duration_readable": format_duration(rs.duration),
                "article_id": rs.article_id,
                "article_title": rs.article.title,
                "article_word_count": rs.article.word_count,
                "article_difficulty": rs.article.fk_difficulty,
                # 'extension' or 'web'; None for sessions from before the field existed
                "reading_source": rs.reading_source,
                "words": bookmarks,
                "word_count": len(bookmarks),
                "interruptions": count,
                "focus_level": _calculate_focus_level(count, rs.duration),
            }
        )
    return sessions


def _exercises_by_session(session_ids, language_id):
    if not session_ids:
        return {}
    exercises = (
        Exercise.query.options(
            joinedload(Exercise.outcome), *_with_meaning(joinedload(Exercise.user_word))
        )
        .filter(Exercise.session_id.in_(session_ids))
        .order_by(Exercise.time)
        .all()
    )
    result = defaultdict(list)
    for ex in exercises:
        if ex.user_word.meaning.origin.language_id == language_id:
            result[ex.session_id].append(ex)
    return result


def _exercise_sessions(user_id, language_id, from_date, to_date):
    exercise_sessions = UserExerciseSession.find_by_user_id(user_id, from_date, to_date)
    exercises = _exercises_by_session([es.id for es in exercise_sessions], language_id)
    # Only sessions with exercises in this language
    exercise_sessions = [es for es in exercise_sessions if exercises.get(es.id)]
    interruptions = _Interruptions(user_id, EVENT_EXERCISE_LOST_FOCUS, exercise_sessions)

    sessions = []
    for es in exercise_sessions:
        words_practiced = [
            {
                # preferred bookmark, so the learner can edit the word
                "id": ex.user_word.preferred_bookmark_id,
                "origin": ex.user_word.meaning.origin.content,
                "translation": ex.user_word.meaning.translation.content,
                # Same definition as the teacher's "correct on 1st try"
                "correct": ExerciseOutcome.is_correct(ex.outcome.outcome),
            }
            for ex in exercises[es.id]
        ]
        total = len(words_practiced)
        correct = sum(1 for w in words_practiced if w["correct"])
        count = interruptions.during(es)
        sessions.append(
            {
                "session_type": "exercise",
                "start_time": es.start_time.isoformat(),
                "duration": es.duration,
                "duration_readable": format_duration(es.duration),
                "words": words_practiced,
                "word_count": total,
                "correct_count": correct,
                "accuracy": round(correct / total * 100),
                "interruptions": count,
                "focus_level": _calculate_focus_level(count, es.duration),
            }
        )
    return sessions


def _browsing_sessions(user_id, language_id, from_date, to_date, for_teacher):
    browsing_sessions = [
        bs
        for bs in UserBrowsingSession.find_by_user(user_id, from_date, to_date)
        # language_id is the learned language when the session started
        if bs.duration and bs.language_id in (None, language_id)
    ]
    words = _words_by_session(
        Bookmark.browsing_session_id,
        [bs.id for bs in browsing_sessions],
        language_id,
        for_teacher,
        with_context=for_teacher,
    )

    sessions = []
    for bs in browsing_sessions:
        bookmarks = words.get(bs.id, [])
        # Browsing without translating (previews, search) still counts: a
        # student who browsed but never opened an article must not look idle.
        # Older sessions have no language; their translations are all we have
        # to go on.
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


def _audio_sessions(user_id, language_id, from_date, to_date):
    # At most one lesson a day, so the per-lesson word lookup stays small.
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
    sessions.sort(key=lambda s: s["start_time"])
    return list(reversed(_merge_consecutive_browsing(sessions)))


def _merge_consecutive_browsing(sessions):
    """
    Every visit to the article list is its own browsing session, so a day of
    using the app leaves a dozen short ones. Back-to-back browsing sessions on
    the same day (nothing else in between) become one entry. Durations add up,
    so totals computed from the list stay exact.

    sessions: in chronological order.
    """
    merged = []
    for session in sessions:
        previous = merged[-1] if merged else None
        if (
            session["session_type"] == "browsing"
            and previous
            and previous["session_type"] == "browsing"
            and previous["start_time"][:10] == session["start_time"][:10]
        ):
            previous["duration"] += session["duration"]
            previous["duration_readable"] = format_duration(previous["duration"])
            previous["words"] += session["words"]
            previous["word_count"] = len(previous["words"])
            previous["merged_sessions"] += 1
            continue
        if session["session_type"] == "browsing":
            session["merged_sessions"] = 1
        merged.append(session)
    return merged
